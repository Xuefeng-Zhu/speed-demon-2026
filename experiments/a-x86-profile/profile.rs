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
    fn getrusage(who: i32, usage: *mut RUsage) -> i32;
    fn clock_gettime(clock: i32, ts: *mut [i64; 2]) -> i32;
}

// ---- Profiling instrumentation (not in production). Key value lines go to stderr. ----
use std::sync::atomic::{AtomicBool, AtomicU64, Ordering::Relaxed};
use std::sync::OnceLock;
use std::time::Instant;

/// Linux x86_64 `struct rusage`: two timevals, then 14 longs.
#[repr(C)]
#[derive(Clone, Copy, Default)]
struct RUsage {
    utime_s: i64,
    utime_us: i64,
    stime_s: i64,
    stime_us: i64,
    maxrss: i64,
    ixrss: i64,
    idrss: i64,
    isrss: i64,
    minflt: i64,
    majflt: i64,
    nswap: i64,
    inblock: i64,
    oublock: i64,
    msgsnd: i64,
    msgrcv: i64,
    nsignals: i64,
    nvcsw: i64,
    nivcsw: i64,
}

const RUSAGE_SELF: i32 = 0;
const RUSAGE_THREAD: i32 = 1;

impl RUsage {
    fn user(&self) -> f64 {
        self.utime_s as f64 + self.utime_us as f64 * 1e-6
    }
    fn sys(&self) -> f64 {
        self.stime_s as f64 + self.stime_us as f64 * 1e-6
    }
}

fn ru(who: i32) -> RUsage {
    let mut r = RUsage::default();
    unsafe { getrusage(who, &mut r) };
    r
}

/// Exact CPU time in seconds (getrusage times are tick-sampled): 2 = process, 3 = this thread.
fn cpu(clock: i32) -> f64 {
    let mut ts = [0i64; 2];
    unsafe { clock_gettime(clock, &mut ts) };
    ts[0] as f64 + ts[1] as f64 * 1e-9
}

static START: OnceLock<Instant> = OnceLock::new();
static SUMMARY_DONE_NS: AtomicU64 = AtomicU64::new(0);

fn now() -> f64 {
    START.get().unwrap().elapsed().as_secs_f64()
}

/// Selected /proc/self/status fields in kB.
fn status_kb(keys: &[&str]) -> Vec<u64> {
    let s = fs::read_to_string("/proc/self/status").unwrap_or_default();
    keys.iter()
        .map(|k| {
            s.lines()
                .find(|l| l.starts_with(k) && l[k.len()..].starts_with(':'))
                .and_then(|l| l[k.len() + 1..].trim().trim_end_matches("kB").trim().parse().ok())
                .unwrap_or(0)
        })
        .collect()
}

const MEM_KEYS: [&str; 6] = ["VmRSS", "VmHWM", "RssAnon", "RssFile", "RssShmem", "VmData"];

/// Process rusage and memory snapshot at a phase boundary.
fn phase(name: &str) {
    let t = now();
    let (r, c) = (ru(RUSAGE_SELF), cpu(2));
    let m = status_kb(&MEM_KEYS);
    eprintln!(
        "phase {name} t={t:.9} cpu={c:.9} utime={:.6} stime={:.6} minflt={} majflt={} nvcsw={} nivcsw={}",
        r.user(), r.sys(), r.minflt, r.majflt, r.nvcsw, r.nivcsw
    );
    let kv: Vec<String> = MEM_KEYS.iter().zip(&m).map(|(k, v)| format!("{k}={v}")).collect();
    eprintln!("mem {name} {}", kv.join(" "));
}

static SAMPLER_STOP: AtomicBool = AtomicBool::new(false);
static SAMPLE_ANON: AtomicU64 = AtomicU64::new(0);
static SAMPLE_ANON_T: AtomicU64 = AtomicU64::new(0);
static SAMPLE_ANON_FILE: AtomicU64 = AtomicU64::new(0);
static SAMPLE_ANON_FILE_T: AtomicU64 = AtomicU64::new(0);
static SAMPLE_TOTAL: AtomicU64 = AtomicU64::new(0);
static SAMPLE_TOTAL_T: AtomicU64 = AtomicU64::new(0);
static SAMPLE_COUNT: AtomicU64 = AtomicU64::new(0);

/// Optional RSS sampler (SD_PROFILE_SAMPLE_US): max of RssAnon, RssAnon+RssFile, and
/// RssAnon+RssFile+RssShmem, with the time each was first reached.
fn start_sampler() -> Option<thread::JoinHandle<()>> {
    let us: u64 = env::var("SD_PROFILE_SAMPLE_US").ok()?.parse().ok()?;
    Some(thread::spawn(move || {
        let keys = ["RssAnon", "RssFile", "RssShmem"];
        while !SAMPLER_STOP.load(Relaxed) {
            let m = status_kb(&keys);
            let t = (now() * 1e9) as u64;
            for (v, max, at) in [
                (m[0], &SAMPLE_ANON, &SAMPLE_ANON_T),
                (m[0] + m[1], &SAMPLE_ANON_FILE, &SAMPLE_ANON_FILE_T),
                (m[0] + m[1] + m[2], &SAMPLE_TOTAL, &SAMPLE_TOTAL_T),
            ] {
                if v > max.load(Relaxed) {
                    max.store(v, Relaxed);
                    at.store(t, Relaxed);
                }
            }
            SAMPLE_COUNT.fetch_add(1, Relaxed);
            thread::sleep(std::time::Duration::from_micros(us));
        }
    }))
}
// ---- End of profiling helpers. ----

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

/// Whether the `len` bytes at `a` and at `b` are equal, compared a word at a time.
#[inline(always)]
fn same(d: &[u8], a: usize, b: usize, len: usize) -> bool {
    let mut i = 0;
    while i + 8 <= len {
        if load(d, a + i) != load(d, b + i) {
            return false;
        }
        i += 8;
    }
    (load(d, a + i) ^ load(d, b + i)) & ((1 << (8 * (len - i))) - 1) == 0
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
            if nh == h && ne - ns == e - s && same(d, ns, s, e - s) {
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
    let (p_start, p_t0, p_r0, p_c0) = (i, now(), ru(RUSAGE_THREAD), cpu(3));
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
    let (p_t1, p_r1, p_c1) = (now(), ru(RUSAGE_THREAD), cpu(3));
    unsafe { madvise(d.as_ptr().add(page), end - page, 4) }; // MADV_DONTNEED
    let (p_t2, p_r2, p_c2) = (now(), ru(RUSAGE_THREAD), cpu(3));
    eprintln!(
        "parse_thread {p_start} bytes={} t_start={p_t0:.9} t_parsed={p_t1:.9} t_end={p_t2:.9} wall={:.9} cpu={:.9} user={:.6} sys={:.6} minflt={} majflt={} nvcsw={} nivcsw={} madv_wall={:.9} madv_cpu={:.9} madv_user={:.6} madv_sys={:.6} madv_minflt={}",
        end - p_start,
        p_t1 - p_t0,
        p_c1 - p_c0,
        p_r1.user() - p_r0.user(),
        p_r1.sys() - p_r0.sys(),
        p_r1.minflt - p_r0.minflt,
        p_r1.majflt - p_r0.majflt,
        p_r1.nvcsw - p_r0.nvcsw,
        p_r1.nivcsw - p_r0.nivcsw,
        p_t2 - p_t1,
        p_c2 - p_c1,
        p_r2.user() - p_r1.user(),
        p_r2.sys() - p_r1.sys(),
        p_r2.minflt - p_r1.minflt,
    );
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
    START.set(Instant::now()).unwrap();
    let sampler = start_sampler();
    phase("start");
    let data_dir = env::var("SD_DATA").unwrap_or_else(|_| "/data".into());
    let out_dir = env::var("SD_OUT").unwrap_or_else(|_| "/out".into());
    let file = fs::File::open(format!("{data_dir}/requests.log")).expect("open requests.log");
    let len = file.metadata().unwrap().len() as usize;
    let d = map_file(&file, len);
    phase("mapped");
    let cpus = thread::available_parallelism().map_or(1, |n| n.get());
    let threads = env::var("SD_THREADS").map_or(cpus, |t| t.parse().unwrap());
    eprintln!("config threads={threads} cpus={cpus} input_bytes={len}");

    let mut cuts = vec![0];
    for t in 1..threads {
        let mut at = (len * t / threads).max(cuts[t - 1]);
        while at > 0 && at < len && d[at - 1] != b'\n' {
            at += 1;
        }
        cuts.push(at);
    }
    cuts.push(len);
    phase("cuts");
    let shared: Vec<Shared> = (0..SHARDS).map(|_| Mutex::default()).collect();
    let mut chunks: Vec<Vec<Records>> = thread::scope(|s| {
        let hs: Vec<_> = cuts
            .windows(2)
            .map(|w| s.spawn(|| parse(d, w[0], w[1], &shared)))
            .collect();
        hs.into_iter().map(|h| h.join().unwrap()).collect()
    });
    phase("parse_done");
    {
        let (mut n, mut esc, mut rc, mut ec, mut buckets) = (0usize, 0usize, 0usize, 0usize, 0usize);
        for (r, e) in chunks.iter().flatten() {
            n += r.len();
            esc += e.len();
            rc += r.capacity() * 4;
            ec += e.capacity() * 8;
            buckets += (r.capacity() > 0) as usize;
        }
        eprintln!(
            "records count={n} escapes={esc} rec_bytes={} rec_cap_bytes={rc} esc_cap_bytes={ec} buckets={buckets}",
            n * 4
        );
    }

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
    phase("merge_done");
    eprintln!(
        "names endpoints={} name_bytes={} rank_bytes={}",
        names.len(),
        names.iter().map(|n| n.len()).sum::<usize>(),
        rank.len() * 4
    );

    // Workers take whole hours, in order, from a queue; this thread writes them out in order.
    let mut f = fs::File::create(format!("{out_dir}/summary.txt")).expect("create summary.txt");
    phase("created");
    let jobs = Mutex::new(jobs.into_iter().enumerate());
    let (tx, rx) = mpsc::channel();
    thread::scope(|s| {
        for w in 0..threads.min(HOURS) {
            let (tx, jobs, rank, names) = (tx.clone(), &jobs, &rank, &names);
            s.spawn(move || {
                let (t0, r0, c0) = (now(), ru(RUSAGE_THREAD), cpu(3));
                let (mut hours, mut busy, mut out_max) = (0, 0.0, 0);
                let mut lat = Vec::new();
                while let Some((h, records)) = { let job = jobs.lock().unwrap().next(); job } {
                    let a = Instant::now();
                    let out = summarize(h, records, rank, names, &mut lat);
                    busy += a.elapsed().as_secs_f64();
                    SUMMARY_DONE_NS.fetch_max((now() * 1e9) as u64, Relaxed);
                    (hours, out_max) = (hours + 1, out_max.max(out.len()));
                    tx.send((h, out)).unwrap();
                }
                let (t1, r1, c1) = (now(), ru(RUSAGE_THREAD), cpu(3));
                eprintln!(
                    "summary_worker {w} hours={hours} t_start={t0:.9} t_end={t1:.9} wall={:.9} busy={busy:.9} cpu={:.9} user={:.6} sys={:.6} minflt={} lat_cap_bytes={} out_max={out_max}",
                    t1 - t0,
                    c1 - c0,
                    r1.user() - r0.user(),
                    r1.sys() - r0.sys(),
                    r1.minflt - r0.minflt,
                    lat.capacity() * 4
                );
            });
        }
        drop(tx);
        let (mut pending, mut written) = (vec![None; HOURS], 0);
        let (mut first_recv, mut write_time, mut bytes, mut writes) = (None, 0.0, 0usize, 0usize);
        let (mut held, mut held_max, mut held_bytes, mut held_bytes_max) = (0usize, 0usize, 0usize, 0usize);
        for (h, out) in rx {
            if first_recv.is_none() {
                first_recv = Some(now());
            }
            (held, held_bytes) = (held + 1, held_bytes + out.capacity());
            (held_max, held_bytes_max) = (held_max.max(held), held_bytes_max.max(held_bytes));
            pending[h] = Some(out);
            while let Some(out) = pending.get_mut(written).and_then(Option::take) {
                let a = Instant::now();
                f.write_all(&out).unwrap();
                write_time += a.elapsed().as_secs_f64();
                (bytes, writes) = (bytes + out.len(), writes + 1);
                (held, held_bytes) = (held - 1, held_bytes - out.capacity());
                if written == 0 {
                    phase("first_written");
                }
                written += 1;
            }
        }
        eprintln!(
            "writes total={write_time:.9} bytes={bytes} count={writes} first_recv={:.9} held_max={held_max} held_cap_bytes_max={held_bytes_max}",
            first_recv.unwrap_or(0.0)
        );
    });
    eprintln!("summary_done t={:.9}", SUMMARY_DONE_NS.load(Relaxed) as f64 * 1e-9);
    phase("done");
    if let Ok(s) = fs::read_to_string("/proc/self/smaps_rollup") {
        let kv: Vec<String> = s
            .lines()
            .skip(1)
            .filter_map(|l| {
                let (k, v) = l.split_once(':')?;
                Some(format!("{k}={}", v.trim().trim_end_matches("kB").trim()))
            })
            .collect();
        eprintln!("rollup done {}", kv.join(" "));
    }
    if let Some(h) = sampler {
        SAMPLER_STOP.store(true, Relaxed);
        h.join().unwrap();
        let ns = |a: &AtomicU64| a.load(Relaxed) as f64 * 1e-9;
        eprintln!(
            "sampler samples={} anon_max={} anon_t={:.9} anon_file_max={} anon_file_t={:.9} total_max={} total_t={:.9}",
            SAMPLE_COUNT.load(Relaxed),
            SAMPLE_ANON.load(Relaxed),
            ns(&SAMPLE_ANON_T),
            SAMPLE_ANON_FILE.load(Relaxed),
            ns(&SAMPLE_ANON_FILE_T),
            SAMPLE_TOTAL.load(Relaxed),
            ns(&SAMPLE_TOTAL_T)
        );
    }
}
