//! Speed Demon 2026, Track A (Ingest): per (hour, endpoint) count, p50/p95/p99 and 5xx rate.
//!
//! 1. mmap the log and split it into one newline-aligned chunk per thread.
//! 2. Each thread parses its chunk into packed records (endpoint id, 5xx bit, latency),
//!    bucketed by hour. A thread's own endpoint table maps to ids from shared maps (sharded by
//!    hash, to spread lock contention) that keep copies of the names, so no merge is needed and
//!    the chunk's pages can be dropped.
//! 3. The shared names are sorted once, so every endpoint id gets its output rank.
//! 4. Threads take whole hours from a queue: counting-sort the hour's latencies by endpoint
//!    rank, select the three nearest-rank percentiles, format the lines, free the records.
use std::collections::HashMap;
use std::sync::{mpsc, Mutex};
use std::{env, fs, io::Write, os::unix::io::AsRawFd, thread};

/// The spec fixes the span: 72 hours from 18:00 UTC on 30 October 2026.
const HOURS: usize = 72;
const ONES: u64 = 0x0101_0101_0101_0101;
const MIX: u64 = 0x9E37_79B9_7F4A_7C15;
/// Shared endpoint id = id within its shard << 4 | shard.
const SHARDS: usize = 16;

extern "C" {
    fn mmap(addr: *mut u8, len: usize, prot: i32, flags: i32, fd: i32, off: i64) -> *mut u8;
    fn madvise(addr: *const u8, len: usize, advice: i32) -> i32;
}

/// Maps the file read-only followed by at least 4 KiB of zeros, so 8-byte loads that run past
/// the last line never fault: an anonymous mapping is reserved and the file mapped over its start.
fn map_file(file: &fs::File, len: usize) -> &'static [u8] {
    let (read, private, fixed, anon, null) = (1, 2, 0x10, 0x20, std::ptr::null_mut());
    unsafe {
        let base = mmap(null, len + 4096, read, private | anon, -1, 0);
        assert!(base as isize > 0, "mmap failed");
        let fd = file.as_raw_fd();
        assert!(len == 0 || mmap(base, len, read, private | fixed, fd, 0) == base);
        std::slice::from_raw_parts(base, len + 4096)
    }
}

/// Little-endian 8-byte load.
#[inline(always)]
fn load(d: &[u8], i: usize) -> u64 {
    assert!(i + 8 <= d.len());
    // SAFETY: in bounds by the assert; any alignment is fine for read_unaligned.
    unsafe { u64::from_le(d.as_ptr().add(i).cast::<u64>().read_unaligned()) }
}

/// Sets the high bit of the first zero byte of `x` (higher bytes may be noise).
#[inline(always)]
fn zero_bytes(x: u64) -> u64 {
    x.wrapping_sub(ONES) & !x & (ONES << 7)
}

/// Index of the first byte equal to `b` in the word `w`, or 8 if none.
#[inline(always)]
fn find_byte(w: u64, b: u8) -> usize {
    (zero_bytes(w ^ (ONES * b as u64)).trailing_zeros() / 8) as usize
}

/// Parses the decimal latency starting at `q`; returns it and the start of the next line.
#[inline(always)]
fn parse_latency(d: &[u8], q: usize) -> (u64, usize) {
    let w = load(d, q);
    let k = find_byte(w, b'\n');
    if k == 8 {
        let (mut v, mut i) = (0, q);
        while d[i] != b'\n' {
            v = v * 10 + (d[i] - b'0') as u64;
            i += 1;
        }
        return (v, i + 1);
    }
    // Shift the k digits up to form an 8-digit number with leading zeros, then combine
    // neighbouring digits, pairs and quads with multiplies (SWAR).
    let mut v = (w ^ (ONES * b'0' as u64)) << (64 - 8 * k);
    v = v * 10 + (v >> 8);
    let lo = (v & 0x0000_00FF_0000_00FF) * (100 + (1_000_000 << 32));
    let hi = ((v >> 16) & 0x0000_00FF_0000_00FF) * (1 + (10_000 << 32));
    (lo.wrapping_add(hi) >> 32, q + k + 1)
}

#[derive(Default)]
/// Open-addressing table from endpoint bytes (byte ranges of the mapped file) to dense ids.
/// An endpoint is identified by its 64-bit hash and its length, not compared byte by byte.
struct Table {
    slots: Vec<u32>,
    names: Vec<(u64, usize, usize)>, // (hash, start, end)
}

impl Table {
    /// Returns the id of endpoint `d[s..e]` (hash `h`), adding it if new.
    fn find(&mut self, d: &[u8], h: u64, s: usize, e: usize) -> usize {
        if self.names.len() * 2 >= self.slots.len() {
            // Grow and reinsert in id order, so ids stay the same.
            self.slots = vec![0; (self.slots.len() * 2).max(1 << 12)];
            for (h, s, e) in std::mem::take(&mut self.names) {
                self.find(d, h, s, e);
            }
        }
        let mask = self.slots.len() - 1;
        let mut i = (h >> 40) as usize & mask;
        while self.slots[i] != 0 {
            let id = self.slots[i] as usize - 1;
            let (nh, ns, ne) = self.names[id];
            if nh == h && ne - ns == e - s {
                return id;
            }
            i = (i + 1) & mask;
        }
        self.names.push((h, s, e));
        self.slots[i] = self.names.len() as u32;
        self.names.len() - 1
    }
}

/// One of the `SHARDS` maps shared by all threads, from (copies of) endpoint names to ids.
type Shared = Mutex<HashMap<Vec<u8>, u32>>;

/// One chunk's records of one hour: `id << 21 | is_5xx << 20 | latency`, or `u32::MAX` for the
/// next escaped record `id << 33 | is_5xx << 32 | latency`.
type Records = (Vec<u32>, Vec<u64>);

/// Parses the lines in `d[i..end]` into records per hour, with ids from the shared tables.
fn parse(d: &[u8], mut i: usize, end: usize, shared: &[Shared]) -> Vec<Records> {
    let page = i & !4095;
    let (mut table, mut ids) = (Table::default(), Vec::new()); // local id -> shared id
    let mut hours = vec![(Vec::new(), Vec::new()); HOURS];
    while i < end {
        let digit = |k: usize| (d[i + k] - b'0') as usize;
        // October 30, 31 and November 1, 2 become day indexes 0..=3.
        let day = digit(8) * 10 + digit(9) + 31 * digit(6) - 30;
        let hour = day * 24 + digit(11) * 10 + digit(12) - 18;
        let s = i + 29 + find_byte(load(d, i + 28), b' ');
        // Find the space after the endpoint a word at a time, hashing the words on the way.
        let (mut e, mut h) = (s, 0u64);
        loop {
            let w = load(d, e);
            let k = find_byte(w, b' ');
            if k < 8 {
                h = (h ^ (w & ((1 << (8 * k)) - 1)) ^ k as u64).wrapping_mul(MIX);
                e += k;
                break;
            }
            h = (h ^ w).wrapping_mul(MIX);
            e += 8;
        }
        let local = table.find(d, h, s, e);
        if local == ids.len() {
            let k = (h >> 60) as usize; // the top 4 bits pick one of 16 shards
            let (name, mut map) = (d[s..e].to_vec(), shared[k].lock().unwrap());
            let n = map.len() as u32;
            ids.push(*map.entry(name).or_insert(n) << 4 | k as u32);
        }
        let id = ids[local] as u64;
        let (latency, next) = parse_latency(d, e + 5);
        let is_5xx = (d[e + 1] == b'5') as u64;
        let (records, escapes) = &mut hours[hour];
        if records.capacity() == 0 {
            records.reserve(1 << 15); // mapped directly, not grown through the allocator's heap
        }
        if id < 2048 && latency < 0x000f_ffff {
            records.push(((id as u32) << 21) | ((is_5xx as u32) << 20) | latency as u32);
        } else {
            records.push(u32::MAX);
            escapes.push(id << 33 | is_5xx << 32 | latency);
        }
        i = next;
    }
    // Drop this chunk's file pages from the mapping now, in parallel, instead of at exit on one
    // thread. Nothing reads these pages again (a read would fault the file back in).
    unsafe { madvise(d.as_ptr().add(page), end - page, 4) }; // MADV_DONTNEED
    hours
}

fn push_num(out: &mut Vec<u8>, mut v: u64) {
    let mut buf = [b' '; 21];
    let mut i = buf.len();
    loop {
        i -= 1;
        buf[i] = b'0' + (v % 10) as u8;
        v /= 10;
        if v == 0 {
            break;
        }
    }
    out.extend_from_slice(&buf[i - 1..]); // includes the leading space separator
}

/// Calls `f(id, is_5xx, latency)` for every record of `chunks`.
#[inline(always)]
fn each(chunks: &[Records], mut f: impl FnMut(usize, u32, u32)) {
    for (records, escapes) in chunks {
        let mut escapes = escapes.iter();
        for &r in records {
            if r == u32::MAX {
                let r = *escapes.next().expect("missing escaped record");
                f((r >> 33) as usize, (r >> 32) as u32 & 1, r as u32);
            } else {
                f((r >> 21) as usize, (r >> 20) & 1, r & 0x000f_ffff);
            }
        }
    }
}

/// Formats every group of one hour from each chunk's records, freeing them as soon as they are
/// sorted. `rank[id]` is an endpoint's output position and `names[rank]` its name. `lat` is the
/// worker's scratch space, kept across hours so its pages fault in only once.
fn summarize(hour: usize, chunks: Vec<Records>, rank: &[u32], names: &[&[u8]], lat: &mut Vec<u32>) -> Vec<u8> {
    let mut start = vec![0u32; names.len() + 1];
    let mut errors = vec![0u32; names.len()];
    each(&chunks, |id, error, _| {
        let g = rank[id] as usize;
        start[g + 1] += 1;
        errors[g] += error;
    });
    for g in 1..start.len() {
        start[g] += start[g - 1];
    }
    lat.resize(*start.last().unwrap() as usize, 0);
    let mut next = start.clone();
    each(&chunks, |id, _, latency| {
        let slot = &mut next[rank[id] as usize];
        lat[*slot as usize] = latency;
        *slot += 1;
    });
    drop(chunks);
    let (day, hh) = ((18 + hour) / 24, (18 + hour) % 24);
    let (month, dd) = (10 + day / 2, [30, 31, 1, 2][day]);
    let prefix = format!("2026-{month:02}-{dd:02}T{hh:02}:00:00Z ");
    let mut out = Vec::with_capacity(1 << 18); // ample for one hour; untouched pages cost nothing
    for (g, name) in names.iter().enumerate() {
        let v = &mut lat[start[g] as usize..start[g + 1] as usize];
        let n = v.len();
        if n == 0 {
            continue;
        }
        let at = |p: usize| (p * n + 99) / 100 - 1;
        let (r50, r95, r99) = (at(50), at(95), at(99));
        if n <= 16 {
            v.sort_unstable();
        } else {
            // Each selection leaves larger values to the right, so later ones search less.
            v.select_nth_unstable(r50);
            if r95 > r50 {
                v[r50 + 1..].select_nth_unstable(r95 - r50 - 1);
            }
            if r99 > r95 {
                v[r95 + 1..].select_nth_unstable(r99 - r95 - 1);
            }
        }
        let e = errors[g] as u64;
        out.extend_from_slice(prefix.as_bytes());
        out.extend_from_slice(name);
        for x in [n as u64, v[r50] as u64, v[r95] as u64, v[r99] as u64, e] {
            push_num(&mut out, x);
        }
        push_num(&mut out, e * 1_000_000 / n as u64);
        out.push(b'\n');
    }
    out
}

fn main() {
    let data_dir = env::var("SD_DATA").unwrap_or_else(|_| "/data".into());
    let out_dir = env::var("SD_OUT").unwrap_or_else(|_| "/out".into());
    let file = fs::File::open(format!("{data_dir}/requests.log")).expect("open requests.log");
    let len = file.metadata().unwrap().len() as usize;
    let d = map_file(&file, len);
    let cpus = thread::available_parallelism().map_or(1, |n| n.get());
    let threads = env::var("SD_THREADS").map_or(cpus, |t| t.parse().unwrap());

    let mut cuts = vec![0];
    for t in 1..threads {
        let mut at = (len * t / threads).max(cuts[t - 1]);
        while at > 0 && at < len && d[at - 1] != b'\n' {
            at += 1;
        }
        cuts.push(at);
    }
    cuts.push(len);
    let shared: Vec<Shared> = (0..SHARDS).map(|_| Mutex::default()).collect();
    let mut chunks: Vec<Vec<Records>> = thread::scope(|s| {
        let hs: Vec<_> = cuts
            .windows(2)
            .map(|w| s.spawn(|| parse(d, w[0], w[1], &shared)))
            .collect();
        hs.into_iter().map(|h| h.join().unwrap()).collect()
    });

    // An endpoint's position in byte order is its output rank.
    let shared: Vec<_> = shared.into_iter().map(|m| m.into_inner().unwrap()).collect();
    let mut names: Vec<(&[u8], usize)> = Vec::new();
    for (k, map) in shared.iter().enumerate() {
        names.extend(map.iter().map(|(name, &id)| (&name[..], (id as usize) << 4 | k)));
    }
    names.sort_unstable();
    let mut rank = vec![0u32; names.iter().map(|&(_, id)| id + 1).max().unwrap_or(0)];
    for (r, &(_, id)) in names.iter().enumerate() {
        rank[id] = r as u32;
    }
    let names: Vec<&[u8]> = names.into_iter().map(|(n, _)| n).collect();
    let jobs: Vec<Vec<Records>> = (0..HOURS)
        .map(|h| chunks.iter_mut().map(|c| std::mem::take(&mut c[h])).collect())
        .collect();

    // Workers take whole hours, in order, from a queue; this thread writes them out in order.
    let mut f = fs::File::create(format!("{out_dir}/summary.txt")).expect("create summary.txt");
    let jobs = Mutex::new(jobs.into_iter().enumerate());
    let (tx, rx) = mpsc::channel();
    thread::scope(|s| {
        for _ in 0..threads.min(HOURS) {
            let (tx, jobs, rank, names) = (tx.clone(), &jobs, &rank, &names);
            s.spawn(move || {
                let mut lat = Vec::new();
                while let Some((h, records)) = { let job = jobs.lock().unwrap().next(); job } {
                    tx.send((h, summarize(h, records, rank, names, &mut lat))).unwrap();
                }
            });
        }
        drop(tx);
        let (mut pending, mut written) = (vec![None; HOURS], 0);
        for (h, out) in rx {
            pending[h] = Some(out);
            while let Some(out) = pending.get_mut(written).and_then(Option::take) {
                f.write_all(&out).unwrap();
                written += 1;
            }
        }
    });
}
