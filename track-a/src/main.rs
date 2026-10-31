//! Speed Demon 2026, Track A (Ingest): per (hour, endpoint) count, p50/p95/p99 and 5xx rate.
//!
//! 1. mmap the log and split it into one newline-aligned chunk per thread.
//! 2. Each thread parses its chunk into packed records (endpoint slot, latency, 5xx bit),
//!    bucketed by hour. All threads share one lock-free endpoint table.
//! 3. The table's endpoints are sorted once; a slot's position in that order is its rank.
//! 4. Each thread takes every T-th hour: gather the hour's latencies by endpoint rank, select
//!    the three nearest-rank percentiles, format the lines and append them in hour order.
//!
//! Work that would be serial at the end is moved into the threads: each one unmaps the input
//! pages it parsed and the record pages it summarised, and nothing is freed before exit.
use std::sync::atomic::{AtomicU64, Ordering::Relaxed};
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
    // Only the bytes before `len` count in the last word.
    let tail_equal = (load(d, a + i) ^ load(d, b + i)) & ((1 << (8 * (len - i))) - 1) == 0;
    len == b_end - b && i + 8 > len && tail_equal
}

/// Parses the decimal latency starting at `q`; returns it and the start of the next line.
fn parse_latency(d: &[u8], q: usize) -> (u64, usize) {
    let w = load(d, q);
    // The first k bytes are digits (k = 8 if the newline is further on). Shift them up into an
    // 8-digit number with leading zeros, then combine neighbouring digits, pairs and quads with
    // multiplies (SWAR).
    let k = find_byte(w, b'\n');
    let mut v = (w ^ (ONES * b'0' as u64)) << (64 - 8 * k);
    v = v * 10 + (v >> 8);
    let lo = (v & 0x0000_00FF_0000_00FF) * (100 + (1_000_000 << 32));
    let hi = ((v >> 16) & 0x0000_00FF_0000_00FF) * (1 + (10_000 << 32));
    let (mut v, mut i) = (lo.wrapping_add(hi) >> 32, q + k);
    while d[i] != b'\n' {
        v = v * 10 + (d[i] - b'0') as u64; // the 9th and 10th digit, if any
        i += 1;
    }
    (v, i + 1)
}

/// Parses the lines in `d[i..end]` into per-hour records `slot << 33 | latency << 1 | is_5xx`.
/// `slots` is the endpoint table shared by all threads: open addressing on the endpoint hash,
/// each slot 0 or `start << 8 | length` of the endpoint's first-inserted copy in `d`. The spec
/// promises 1,842 endpoints; the table has no check for more than its 8,192 slots.
fn parse(d: &[u8], mut i: usize, end: usize, slots: &[AtomicU64]) -> Vec<Vec<u64>> {
    // MADV_POPULATE_READ = 22 (Linux 5.14+; on older kernels the pages fault in lazily).
    let page = i & !4095;
    unsafe { madvise(d.as_ptr().add(page), end - page, 22) };
    let mut hours = vec![vec![]; HOURS];
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
        let mut slot = (h >> 51) as usize; // the top 13 bits
        loop {
            let v = slots[slot].load(Relaxed) as usize;
            if v == 0 {
                // Claim the slot, then compare with whoever won it on the next pass.
                let new = (s << 8 | (e - s)) as u64;
                let _ = slots[slot].compare_exchange(0, new, Relaxed, Relaxed);
            } else if same(d, (v >> 8, (v >> 8) + (v & 255)), (s, e)) {
                break;
            } else {
                slot = (slot + 1) % slots.len();
            }
        }
        let (latency, next) = parse_latency(d, e + 5);
        hours[hour].push((slot as u64) << 33 | latency << 1 | (d[e + 1] == b'5') as u64);
        i = next;
    }
    // MADV_DONTNEED = 4: unmap this chunk's pages now, in parallel, rather than serially at exit.
    // A later read of an endpoint name faults its page back in from the file.
    unsafe { madvise(d.as_ptr().add(page), end - page, 4) };
    hours
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

/// Formats every group of one hour. `groups` is scratch space, one empty vector per endpoint,
/// that the caller keeps across hours so the vectors keep their capacity.
fn summarize(
    hour: usize,
    chunks: &[Vec<Vec<u64>>],
    (rank, names): (&[u32], &[&[u8]]),
    groups: &mut [(Vec<u32>, u64)],
) -> Vec<u8> {
    // Each group collects its latencies and counts its 5xx responses.
    for hours in chunks {
        for &r in &hours[hour] {
            let (v, errors) = &mut groups[rank[(r >> 33) as usize] as usize];
            v.push((r >> 1) as u32);
            *errors += r & 1;
        }
        // The records are not read again: return their whole pages now, in parallel, rather
        // than serially at exit (MADV_DONTNEED; the allocator's headers are outside them).
        let r = hours[hour].as_ptr_range();
        let (a, b) = ((r.start as usize + 4095) & !4095, r.end as usize & !4095);
        unsafe { madvise(a as *const u8, b.saturating_sub(a), 4) };
    }
    let (day, hh) = ((18 + hour) / 24, (18 + hour) % 24);
    let (month, dd) = (10 + day / 2, [30, 31, 1, 2][day]);
    let prefix = format!("2026-{month:02}-{dd:02}T{hh:02}:00:00Z ");
    let mut out = Vec::with_capacity(1 << 18);
    for (name, (v, e)) in names.iter().zip(groups).filter(|(_, (v, _))| !v.is_empty()) {
        let (n, e) = (v.len(), std::mem::take(e));
        let [r50, r95, r99] = [50, 95, 99].map(|p| (p * n + 99) / 100 - 1);
        // Each selection leaves the larger values to its right, so later ones search less.
        let p50 = *v.select_nth_unstable(r50).1 as u64;
        let p95 = *v[r50..].select_nth_unstable(r95 - r50).1 as u64;
        let p99 = *v[r95..].select_nth_unstable(r99 - r95).1 as u64;
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
    // The spec has 1,842 endpoints per seed, so 8,192 slots stay under a quarter full.
    let slots: Vec<_> = (0..1 << 13).map(|_| AtomicU64::new(0)).collect();
    let chunks = par(threads, |t| parse(d, cut(t), cut(t + 1), &slots));

    // An endpoint's position in byte order is its output rank.
    let name = |k: &usize| {
        let v = slots[*k].load(Relaxed) as usize;
        &d[v >> 8..(v >> 8) + (v & 255)]
    };
    let mut order: Vec<usize> = (0..slots.len()).filter(|&k| !name(&k).is_empty()).collect();
    order.sort_unstable_by_key(name);
    let names: Vec<_> = order.iter().map(name).collect();
    let mut rank = vec![0u32; slots.len()];
    order
        .iter()
        .enumerate()
        .for_each(|(r, &k)| rank[k] = r as u32);

    // Thread t summarises hours t, t + T, t + 2T, ... and sends them over its own channel, so
    // this thread receives hour h from channel h % T and writes the hours out in order.
    let workers = threads.min(HOURS);
    let (txs, rxs): (Vec<_>, Vec<_>) = (0..workers).map(|_| mpsc::channel::<Vec<u8>>()).unzip();
    let mut f = fs::File::create(format!("{out_dir}/summary.txt"))?;
    thread::scope(|s| {
        s.spawn(|| {
            par(workers, |t| {
                let mut groups = vec![(vec![], 0); names.len()];
                for hour in (t..HOURS).step_by(workers) {
                    let out = summarize(hour, &chunks, (&rank, &names), &mut groups);
                    txs[t].send(out).unwrap();
                }
            })
        });
        (0..HOURS).try_for_each(|h| f.write_all(&rxs[h % workers].recv().unwrap()))
    })?;
    std::process::exit(0) // skips freeing: the kernel reclaims everything at once
}
