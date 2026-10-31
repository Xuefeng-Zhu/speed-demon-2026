//! Speed Demon 2026, Track A (Ingest): per (hour, endpoint) count, p50/p95/p99 and 5xx rate.
//!
//! 1. mmap the log and split it into one newline-aligned chunk per thread.
//! 2. Each thread parses its chunk into packed records (endpoint id, 5xx bit, latency),
//!    bucketed by hour, with its own endpoint table.
//! 3. All endpoint names are sorted once; each chunk's ids map to their output rank.
//! 4. Each thread takes every T-th hour: gather the hour's latencies by endpoint rank, select
//!    the three nearest-rank percentiles, format the lines and append them in hour order.
use std::{env, fs, io::Write, os::unix::io::AsRawFd, ptr::null_mut, sync::mpsc, thread};

/// The spec fixes the span: 72 hours from 18:00 UTC on 30 October 2026.
const HOURS: usize = 72;
const ONES: u64 = 0x0101_0101_0101_0101;

extern "C" {
    fn mmap(addr: *mut u8, len: usize, prot: i32, flags: i32, fd: i32, off: i64) -> *mut u8;
    fn madvise(addr: *const u8, len: usize, advice: i32) -> i32;
}

/// Maps the file read-only followed by at least 4 KiB of zeros, so 8-byte loads that run past
/// the last line never fault: an anonymous mapping is reserved and the file mapped over its start.
fn map_file(file: &fs::File, len: usize) -> &'static [u8] {
    // PROT_READ = 1, MAP_PRIVATE | MAP_ANONYMOUS = 0x22, MAP_PRIVATE | MAP_FIXED = 0x12.
    unsafe {
        let base = mmap(null_mut(), len + 4096, 1, 0x22, -1, 0);
        assert!(base as isize > 0, "mmap failed");
        assert!(len == 0 || mmap(base, len, 1, 0x12, file.as_raw_fd(), 0) == base);
        std::slice::from_raw_parts(base, len + 4096)
    }
}

/// Runs `f(0..n)` on n scoped threads and collects the results in order.
fn par<T: Send>(n: usize, f: impl Fn(usize) -> T + Sync) -> Vec<T> {
    let f = &f;
    thread::scope(|s| {
        let hs: Vec<_> = (0..n).map(|t| s.spawn(move || f(t))).collect();
        hs.into_iter().map(|h| h.join().unwrap()).collect()
    })
}

/// Little-endian 8-byte load.
#[inline(always)]
fn load(d: &[u8], i: usize) -> u64 {
    assert!(i + 8 <= d.len());
    // SAFETY: in bounds by the assert; read_unaligned accepts any alignment.
    unsafe { u64::from_le(d.as_ptr().add(i).cast::<u64>().read_unaligned()) }
}

/// Index of the first byte equal to `b` in the word `w`, or 8 if none (SWAR zero-byte test).
fn find_byte(w: u64, b: u8) -> usize {
    let x = w ^ (ONES * b as u64);
    (x.wrapping_sub(ONES) & !x & (ONES << 7)).trailing_zeros() as usize / 8
}

/// Whether the byte ranges `d[a..a_end]` and `d[b..b_end]` are equal, compared a word at a time.
fn same(d: &[u8], (a, a_end): (usize, usize), (b, b_end): (usize, usize)) -> bool {
    let (len, mut i) = (a_end - a, 0);
    while i + 8 <= len && load(d, a + i) == load(d, b + i) {
        i += 8;
    }
    // Only compare a tail after matching lengths and every complete word.
    len == b_end - b && i + 8 > len
        && (load(d, a + i) ^ load(d, b + i)) & ((1 << (8 * (len - i))) - 1) == 0
}

/// Parses the decimal latency starting at `q`; returns it and the start of the next line.
fn parse_latency(d: &[u8], q: usize) -> (u64, usize) {
    let w = load(d, q);
    // The first k bytes are digits (k = 8 if the newline is further on). Shift them up into an
    // 8-digit number with leading zeros, then combine neighbouring digits, pairs and quads with
    // multiplies (SWAR).
    let k = find_byte(w, b'\n');
    let mut v = (w ^ (ONES * b'0' as u64)) << (64 - 8 * k);
    v = v.wrapping_mul(10).wrapping_add(v >> 8);
    let lo = (v & 0x0000_00FF_0000_00FF).wrapping_mul(100 + (1_000_000 << 32));
    let hi = ((v >> 16) & 0x0000_00FF_0000_00FF).wrapping_mul(1 + (10_000 << 32));
    let (mut v, mut i) = (lo.wrapping_add(hi) >> 32, q + k);
    while d[i] != b'\n' {
        v = v * 10 + (d[i] - b'0') as u64; // the 9th and 10th digit, if any
        i += 1;
    }
    (v, i + 1)
}

/// Parses the lines in `d[i..end]`. Returns the chunk's endpoints as byte ranges `(start, end)`
/// indexed by id, and per hour the records `id << 33 | latency << 1 | is_5xx`.
fn parse(d: &[u8], mut i: usize, end: usize) -> (Vec<(usize, usize)>, Vec<Vec<u64>>) {
    // MADV_POPULATE_READ = 22 (Linux 5.14+; on older kernels the pages fault in lazily).
    let page = i & !4095;
    unsafe { madvise(d.as_ptr().add(page), end - page, 22) };
    // Open addressing from endpoint hash to id + 1; grow while preserving ids.
    let (mut slots, mut names, mut hashes, mut hours) = (vec![0u32; 1 << 13], vec![], vec![], vec![vec![]; HOURS]);
    let hash_slot = |h: u64, len: usize| (h >> (64 - len.trailing_zeros())) as usize;
    while i < end {
        let digit = |k: usize| (d[i + k] - b'0') as usize;
        // October 30, 31 and November 1, 2 become day indexes 0..=3.
        let day = digit(8) * 10 + digit(9) + 31 * digit(6) - 30;
        let hour = day * 24 + digit(11) * 10 + digit(12) - 18;
        // The method is 3 to 7 bytes, so the space after it is in the word at i + 28.
        let s = i + 29 + find_byte(load(d, i + 28), b' ');
        // Find the space after the endpoint a word at a time, hashing the words on the way.
        let (mut e, mut h) = (s, 0u64);
        loop {
            let w = load(d, e);
            let k = find_byte(w, b' ');
            let w = if k < 8 { w & ((1 << (8 * k)) - 1) } else { w };
            h = (h ^ w).wrapping_mul(0x9E37_79B9_7F4A_7C15);
            e += k;
            if k < 8 {
                break;
            }
        }
        if names.len() >= slots.len() / 2 {
            slots = vec![0; slots.len() * 2];
            for (id, &old_hash) in hashes.iter().enumerate() {
                let mut slot = hash_slot(old_hash, slots.len());
                while slots[slot] != 0 { slot = (slot + 1) % slots.len(); }
                slots[slot] = id as u32 + 1;
            }
        }
        let mut slot = hash_slot(h, slots.len());
        while slots[slot] != 0 && !same(d, names[slots[slot] as usize - 1], (s, e)) {
            slot = (slot + 1) % slots.len();
        }
        if slots[slot] == 0 {
            names.push((s, e));
            hashes.push(h);
            slots[slot] = names.len() as u32;
        }
        let id = slots[slot] as u64 - 1;
        let (latency, next) = parse_latency(d, e + 5);
        hours[hour].push(id << 33 | latency << 1 | (d[e + 1] == b'5') as u64);
        i = next;
    }
    (names, hours)
}

/// Appends a space and the decimal digits of `v`.
fn push_num(out: &mut Vec<u8>, v: u64) {
    if v >= 10 {
        push_num(out, v / 10);
    } else {
        out.push(b' ');
    }
    out.push(b'0' + (v % 10) as u8);
}

/// One parsed chunk after the merge: each endpoint id's output rank, and the hourly records.
type Chunk = (Vec<u32>, Vec<Vec<u64>>);

/// Formats every group of one hour. `groups` is scratch space, one empty vector per endpoint,
/// that the caller keeps across hours so the vectors keep their capacity.
fn summarize(hour: usize, chunks: &[Chunk], names: &[&[u8]], groups: &mut [Vec<u64>]) -> Vec<u8> {
    // Each group collects its `latency << 1 | is_5xx` values. These sort by latency, so the
    // percentiles are read off with `>> 1` and the error count is the sum of the low bits.
    for (rank, hours) in chunks {
        for &r in &hours[hour] {
            groups[rank[(r >> 33) as usize] as usize].push(r & ((1 << 33) - 1));
        }
    }
    let (day, hh) = ((18 + hour) / 24, (18 + hour) % 24);
    let (month, dd) = (10 + day / 2, [30, 31, 1, 2][day]);
    let prefix = format!("2026-{month:02}-{dd:02}T{hh:02}:00:00Z ");
    let mut out = Vec::with_capacity(1 << 18);
    for (name, v) in names.iter().zip(groups).filter(|(_, v)| !v.is_empty()) {
        let (n, e) = (v.len(), v.iter().map(|x| x & 1).sum::<u64>());
        let [r50, r95, r99] = [50, 95, 99].map(|p| (p * n + 99) / 100 - 1);
        // Each selection leaves the larger values to its right, so later ones search less.
        let p50 = *v.select_nth_unstable(r50).1 >> 1;
        let p95 = *v[r50..].select_nth_unstable(r95 - r50).1 >> 1;
        let p99 = *v[r95..].select_nth_unstable(r99 - r95).1 >> 1;
        v.clear();
        out.extend_from_slice(prefix.as_bytes());
        out.extend_from_slice(name);
        for x in [n as u64, p50, p95, p99, e, e * 1_000_000 / n as u64] {
            push_num(&mut out, x);
        }
        out.push(b'\n');
    }
    out
}

fn main() -> std::io::Result<()> {
    let data_dir = env::var("SD_DATA").unwrap_or_else(|_| "/data".into());
    let out_dir = env::var("SD_OUT").unwrap_or_else(|_| "/out".into());
    let file = fs::File::open(format!("{data_dir}/requests.log"))?;
    let len = file.metadata()?.len() as usize;
    let d = map_file(&file, len);
    let cpus = thread::available_parallelism().map_or(1, |n| n.get());
    let threads = env::var("SD_THREADS").map_or(cpus, |t| t.parse().unwrap());

    // Chunk t starts at the first line at or after byte len * t / threads.
    let cut = |t| {
        (len * t / threads..len)
            .find(|&at| at == 0 || d[at - 1] == b'\n')
            .unwrap_or(len)
    };
    let chunks = par(threads, |t| parse(d, cut(t), cut(t + 1)));

    // An endpoint's position in byte order is its output rank.
    let mut names: Vec<&[u8]> = vec![];
    for (ids, _) in &chunks {
        names.extend(ids.iter().map(|&(s, e)| &d[s..e]));
    }
    names.sort_unstable();
    names.dedup();
    let rank = |&(s, e): &(usize, usize)| names.binary_search(&&d[s..e]).unwrap() as u32;
    let chunks: Vec<Chunk> = chunks
        .into_iter()
        .map(|(ids, hours)| (ids.iter().map(rank).collect(), hours))
        .collect();

    // Thread t summarises hours t, t + T, t + 2T, ... and sends them over its own channel, so
    // this thread receives hour h from channel h % T and writes the hours out in order.
    let workers = threads.min(HOURS);
    let (txs, rxs): (Vec<_>, Vec<_>) = (0..workers).map(|_| mpsc::channel::<Vec<u8>>()).unzip();
    let mut f = fs::File::create(format!("{out_dir}/summary.txt"))?;
    thread::scope(|s| {
        s.spawn(|| {
            par(workers, |t| {
                let mut groups = vec![vec![]; names.len()];
                for hour in (t..HOURS).step_by(workers) {
                    let out = summarize(hour, &chunks, &names, &mut groups);
                    txs[t].send(out).unwrap();
                }
            })
        });
        (0..HOURS).try_for_each(|h| f.write_all(&rxs[h % workers].recv().unwrap()))
    })
}
