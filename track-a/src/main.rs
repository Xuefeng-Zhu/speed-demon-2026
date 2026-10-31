//! Speed Demon 2026, Track A (Ingest): per (hour, endpoint) count, p50/p95/p99 and 5xx rate.
//!
//! 1. mmap the log and split it into one newline-aligned chunk per thread.
//! 2. Each thread parses its chunk into packed records (endpoint id, 5xx bit, latency),
//!    bucketed by hour. A thread's own endpoint table caches the dense ids (0, 1, 2, ...) handed
//!    out by shared maps (sharded by hash, to spread lock contention) that keep copies of the
//!    names, so no merge is needed and the chunk's pages can be dropped.
//! 3. The same threads then meet at a barrier; one sorts the shared names once, so every
//!    endpoint id gets its output rank, and regroups the records by hour.
//! 4. The threads take whole hours from a queue: count the hour's records per endpoint id,
//!    counting-sort its latencies into groups laid out in rank order, find the three
//!    nearest-rank percentiles (branch-free AVX2 rank counting for groups of up to 64 values,
//!    selection otherwise), format the lines, free the records. The main thread writes the
//!    hours in order.
use std::collections::HashMap;
use std::sync::{atomic::{AtomicU32, Ordering}, mpsc, Barrier, Mutex, OnceLock};
use std::{env, fs, io::Write, os::unix::io::AsRawFd, thread};

/// The spec fixes the span: 72 hours from 18:00 UTC on 30 October 2026.
const HOURS: usize = 72;
const ONES: u64 = 0x0101_0101_0101_0101;
const MIX: u64 = 0x9E37_79B9_7F4A_7C15;

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

/// Bit `k` is set iff `a[i + k] == b[j + k]` (`b == None`: iff `a[i + k] == c`), for `k` in 0..64.
/// Reads 64 bytes at `i` (and `j`). In the file, callers start inside a line (at an endpoint),
/// so the reads end at most 64 bytes past the last line, within the 4 KiB zero pad of
/// `map_file`; arena reads stay within its 64-byte zero tail.
#[inline(always)]
fn eq_mask(a: &[u8], i: usize, b: Option<(&[u8], usize)>, c: u8) -> u64 {
    assert!(i + 64 <= a.len() && b.map_or(true, |(b, j)| j + 64 <= b.len()));
    #[cfg(all(target_arch = "x86_64", target_feature = "avx2"))]
    // SAFETY: in bounds by the assert; AVX2 is enabled at compile time; loads are unaligned.
    unsafe {
        use std::arch::x86_64::*;
        let load = |d: &[u8], i: usize| _mm256_loadu_si256(d.as_ptr().add(i).cast());
        let other = |k: usize| b.map_or(_mm256_set1_epi8(c as i8), |(b, j)| load(b, j + k));
        let half = |k| _mm256_movemask_epi8(_mm256_cmpeq_epi8(load(a, i + k), other(k))) as u32;
        half(0) as u64 | (half(32) as u64) << 32
    }
    #[cfg(not(all(target_arch = "x86_64", target_feature = "avx2")))]
    (0..64).fold(0, |m, k| m | ((a[i + k] == b.map_or(c, |(b, j)| b[j + k])) as u64) << k)
}

/// Hash of the endpoint of `n` bytes at `s`, from its first and last words and length.
#[inline(always)]
fn hash(d: &[u8], s: usize, n: usize) -> u64 {
    let h = if n >= 8 {
        load(d, s) ^ load(d, s + n - 8).rotate_left(29)
    } else {
        load(d, s) & ((1 << (8 * n)) - 1)
    };
    (h ^ n as u64).wrapping_mul(MIX)
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
/// Open-addressing table from endpoint bytes to shared ids. Each entry lives in one compact
/// arena: hash (8 bytes), length and shared id (4 bytes each), then the name padded to 8 bytes,
/// so a probe touches one or two adjacent cache lines. The arena ends with 64 zero bytes so
/// `eq_mask` may read past the last name.
struct Table {
    slots: Vec<usize>,   // 1 + offset of the entry in `arena`, or 0 if empty
    entries: Vec<usize>, // entry offsets, for regrowing
    arena: Vec<u8>,
}

impl Table {
    /// Returns the shared id of endpoint `d[s..e]` (hash `h`), asking `new` for it if unseen.
    #[inline(always)]
    fn find(&mut self, d: &[u8], h: u64, s: usize, e: usize, new: impl FnOnce() -> u32) -> u32 {
        if self.entries.len() * 2 >= self.slots.len() {
            self.grow();
        }
        let (mask, n) = (self.slots.len() - 1, e - s);
        let mut i = (h >> 40) as usize & mask;
        while self.slots[i] != 0 {
            let at = self.slots[i] - 1;
            let (nh, meta) = (load(&self.arena, at), load(&self.arena, at + 8));
            if nh == h
                && meta as u32 as usize == n
                && if n < 64 {
                    !eq_mask(&self.arena, at + 16, Some((d, s)), 0) & ((1 << n) - 1) == 0
                } else if n < 128 {
                    // The second read ends within the name's own 64-byte zero tail.
                    !eq_mask(&self.arena, at + 16, Some((d, s)), 0) == 0
                        && !eq_mask(&self.arena, at + 80, Some((d, s + 64)), 0) & ((1 << (n - 64)) - 1) == 0
                } else {
                    self.arena[at + 16..at + 16 + n] == d[s..e]
                }
            {
                return (meta >> 32) as u32;
            }
            i = (i + 1) & mask;
        }
        let id = new();
        let at = self.arena.len().saturating_sub(64);
        self.arena.truncate(at);
        self.arena.extend_from_slice(&h.to_le_bytes());
        self.arena.extend_from_slice(&(n as u32).to_le_bytes());
        self.arena.extend_from_slice(&id.to_le_bytes());
        self.arena.extend_from_slice(&d[s..e]);
        self.arena.resize((self.arena.len() + 7) / 8 * 8 + 64, 0);
        self.entries.push(at);
        self.slots[i] = at + 1;
        id
    }

    #[cold]
    fn grow(&mut self) {
        self.slots = vec![0; (self.slots.len() * 2).max(1 << 12)];
        let mask = self.slots.len() - 1;
        for &at in &self.entries {
            let mut i = (load(&self.arena, at) >> 40) as usize & mask;
            while self.slots[i] != 0 {
                i = (i + 1) & mask;
            }
            self.slots[i] = at + 1;
        }
    }
}

/// One of 16 maps shared by all threads (sharded by hash, to spread lock contention), from
/// (copies of) endpoint names to dense ids 0, 1, 2, ... handed out by one atomic counter.
type Shared = Mutex<HashMap<Vec<u8>, u32>>;
const SHARDS: usize = 16;

/// One chunk's records of one hour: `id << 21 | is_5xx << 20 | latency`, or `u32::MAX` for the
/// next escaped record `id << 33 | is_5xx << 32 | latency`.
type Records = (Vec<u32>, Vec<u64>);

/// Parses the lines in `d[i..end]` into records per hour, with ids from the shared tables.
fn parse(d: &[u8], mut i: usize, end: usize, shared: &[Shared], next_id: &AtomicU32) -> Vec<Records> {
    let page = i & !4095;
    let mut table = Table::default();
    let mut hours = vec![(Vec::new(), Vec::new()); HOURS];
    while i < end {
        // Bytes 5..13 are "MM-DDTHH"; their low nibbles x make 10 * x[k] + x[k + 1] in byte k of
        // y without carries. October 30, 31 and November 1, 2 become day indexes 0..=3.
        let x = load(d, i + 5) & (ONES * 0x0f);
        let y = x * 10 + (x >> 8);
        let day = (y >> 24 & 0xff) + 31 * (x >> 8 & 0xff) - 30;
        let hour = (day * 24 + (y >> 48 & 0xff) - 18) as usize;
        let s = i + 29 + find_byte(load(d, i + 28), b' ');
        // The space after the endpoint: among the next 64 or 128 bytes, else a word at a time.
        let mut e = s + eq_mask(d, s, None, b' ').trailing_zeros() as usize;
        if e == s + 64 {
            e += eq_mask(d, e, None, b' ').trailing_zeros() as usize;
            if e == s + 128 {
                while find_byte(load(d, e), b' ') == 8 {
                    e += 8;
                }
                e += find_byte(load(d, e), b' ');
            }
        }
        let h = hash(d, s, e - s);
        let id = table.find(d, h, s, e, || {
            let mut map = shared[(h >> 60) as usize].lock().unwrap(); // top 4 bits pick a shard
            *map.entry(d[s..e].to_vec()).or_insert_with(|| next_id.fetch_add(1, Ordering::Relaxed))
        }) as u64;
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

/// Two-digit decimal strings "00" to "99".
const PAIRS: &[u8; 200] = b"0001020304050607080910111213141516171819\
2021222324252627282930313233343536373839\
4041424344454647484950515253545556575859\
6061626364656667686970717273747576777879\
8081828384858687888990919293949596979899";

/// Writes " " and the decimal digits of `v` at `b[at..]`; returns the index past them.
#[inline(always)]
fn put_num(b: &mut [u8], at: usize, mut v: u64) -> usize {
    b[at] = b' ';
    let end = at + 2 + v.checked_ilog10().unwrap_or(0) as usize;
    let mut i = end;
    while v >= 100 {
        let p = (v % 100) as usize * 2;
        v /= 100;
        i -= 2;
        b[i..i + 2].copy_from_slice(&PAIRS[p..p + 2]);
    }
    if v >= 10 {
        b[i - 2..i].copy_from_slice(&PAIRS[v as usize * 2..v as usize * 2 + 2]);
    } else {
        b[i - 1] = b'0' + v as u8;
    }
    end
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

/// The values of ranks `r` (0-based) among the at most `8 * V` values of `v`, with AVX2: the
/// value of rank r is the largest value with at most r values below it, so one branch-free count
/// per value replaces sorting. Reads `8 * V` values from the start of `v`, so the caller's buffer
/// must extend at least that far past it.
#[cfg(all(target_arch = "x86_64", target_feature = "avx2"))]
#[inline(always)]
fn small_ranks<const V: usize>(lat: &[u32], at: usize, n: usize, r: [usize; 3]) -> [u32; 3] {
    use std::arch::x86_64::*;
    assert!(n <= 8 * V && at + 8 * V <= lat.len());
    // SAFETY: loads are in bounds by the assert and unaligned; AVX2 is enabled at compile time.
    unsafe {
        // Unsigned order via signed compares of biased values; lanes past n become u32::MAX,
        // which is never below a value (and is the right answer whenever it gets counted).
        let bias = _mm256_set1_epi32(i32::MIN);
        let x: [__m256i; V] = std::array::from_fn(|k| {
            let lane = _mm256_setr_epi32(0, 1, 2, 3, 4, 5, 6, 7);
            let live = _mm256_cmpgt_epi32(_mm256_set1_epi32(n as i32 - 8 * k as i32), lane);
            let w = _mm256_loadu_si256(lat.as_ptr().add(at + 8 * k).cast());
            _mm256_xor_si256(_mm256_blendv_epi8(_mm256_set1_epi32(-1), w, live), bias)
        });
        let mut below = [_mm256_setzero_si256(); V];
        for &y in &lat[at..at + n] {
            let y = _mm256_set1_epi32((y ^ 1 << 31) as i32);
            for k in 0..V {
                below[k] = _mm256_sub_epi32(below[k], _mm256_cmpgt_epi32(x[k], y));
            }
        }
        r.map(|r| {
            let r = _mm256_set1_epi32(r as i32);
            let mut m = _mm256_setzero_si256();
            for k in 0..V {
                let over = _mm256_cmpgt_epi32(below[k], r);
                m = _mm256_max_epu32(m, _mm256_andnot_si256(over, _mm256_xor_si256(x[k], bias)));
            }
            let m = _mm256_max_epu32(m, _mm256_permute2x128_si256(m, m, 1));
            let m = _mm256_max_epu32(m, _mm256_shuffle_epi32(m, 0b01_00_11_10));
            let m = _mm256_max_epu32(m, _mm256_shuffle_epi32(m, 0b10_11_00_01));
            _mm256_cvtsi256_si32(m) as u32
        })
    }
}

/// The values of ranks `r` (0-based) among `v`.
#[inline(always)]
fn select_ranks(v: &mut [u32], [r50, r95, r99]: [usize; 3]) -> [u32; 3] {
    if v.len() <= 16 {
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
    [v[r50], v[r95], v[r99]]
}

/// A summary worker's buffers, kept across hours so their pages fault in only once.
#[derive(Default)]
struct Scratch {
    counts: Vec<u64>, // per id: records | errors << 32
    next: Vec<u32>,   // per id: next free slot of its group in `lat`
    lat: Vec<u32>,
}

/// Formats every group of one hour from each chunk's records, freeing them as soon as they are
/// sorted. `order[rank]` is the id of the endpoint at output position `rank`, `names[rank]` its name.
fn summarize(hour: usize, chunks: Vec<Records>, order: &[u32], names: &[Vec<u8>], s: &mut Scratch) -> Vec<u8> {
    let Scratch { counts, next, lat } = s;
    counts.clear();
    counts.resize(order.len(), 0);
    each(&chunks, |id, error, _| counts[id] += 1 | (error as u64) << 32);
    // Groups are laid out in rank order, but looked up by id.
    next.resize(order.len(), 0);
    let mut total = 0;
    for &id in order {
        next[id as usize] = total;
        total += counts[id as usize] as u32;
    }
    lat.resize(total as usize + 64, 0); // `small_ranks` reads up to 64 values past a group
    each(&chunks, |id, _, latency| {
        let slot = &mut next[id];
        lat[*slot as usize] = latency;
        *slot += 1;
    });
    drop(chunks);
    let (day, hh) = ((18 + hour) / 24, (18 + hour) % 24);
    let (month, dd) = (10 + day / 2, [30, 31, 1, 2][day]);
    let prefix = format!("2026-{month:02}-{dd:02}T{hh:02}:00:00Z ");
    let mut out = Vec::with_capacity(1 << 18); // ample for one hour; untouched pages cost nothing
    let mut line = [0u8; 512]; // prefix (21) + name (at most 125 by spec) + 6 numbers
    line[..prefix.len()].copy_from_slice(prefix.as_bytes());
    for (g, name) in names.iter().enumerate() {
        let id = order[g] as usize;
        let n = counts[id] as u32 as usize;
        if n == 0 {
            continue;
        }
        let at = next[id] as usize - n;
        let rank = |p: usize| (p * n + 99) / 100 - 1;
        let r = [rank(50), rank(95), rank(99)];
        #[cfg(all(target_arch = "x86_64", target_feature = "avx2"))]
        let [p50, p95, p99] = match n {
            0..=8 => small_ranks::<1>(lat, at, n, r),
            9..=16 => small_ranks::<2>(lat, at, n, r),
            17..=32 => small_ranks::<4>(lat, at, n, r),
            33..=64 => small_ranks::<8>(lat, at, n, r),
            _ => select_ranks(&mut lat[at..at + n], r),
        };
        #[cfg(not(all(target_arch = "x86_64", target_feature = "avx2")))]
        let [p50, p95, p99] = select_ranks(&mut lat[at..at + n], r);
        let e = counts[id] >> 32;
        if prefix.len() + name.len() + 6 * 21 + 1 > line.len() {
            // Longer than the spec allows; format it the slow way.
            out.extend_from_slice(prefix.as_bytes());
            out.extend_from_slice(name);
            for x in [n as u64, p50 as u64, p95 as u64, p99 as u64, e, e * 1_000_000 / n as u64] {
                out.extend_from_slice(format!(" {x}").as_bytes());
            }
            out.push(b'\n');
            continue;
        }
        let mut k = prefix.len() + name.len();
        line[prefix.len()..k].copy_from_slice(name);
        for x in [n as u64, p50 as u64, p95 as u64, p99 as u64, e, e * 1_000_000 / n as u64] {
            k = put_num(&mut line, k, x);
        }
        line[k] = b'\n';
        out.extend_from_slice(&line[..k + 1]);
    }
    out
}

/// The hours still to summarize, in order, each with every chunk's records.
type Jobs = Mutex<std::iter::Enumerate<std::vec::IntoIter<Vec<Records>>>>;

/// Once every chunk is parsed: sorts the endpoint names (an endpoint's position in byte order is
/// its output rank) and regroups the records by hour. Returns the id of each rank, the names in
/// rank order and the jobs.
fn make_plan(shared: &[Shared], parsed: &[Mutex<Vec<Records>>]) -> (Vec<u32>, Vec<Vec<u8>>, Jobs) {
    let mut names: Vec<(Vec<u8>, u32)> = Vec::new();
    for map in shared {
        names.extend(std::mem::take(&mut *map.lock().unwrap()));
    }
    names.sort_unstable();
    let order = names.iter().map(|&(_, id)| id).collect(); // ids are exactly 0..names.len()
    let names = names.into_iter().map(|(name, _)| name).collect();
    let mut chunks: Vec<Vec<Records>> = parsed.iter().map(|c| std::mem::take(&mut *c.lock().unwrap())).collect();
    let jobs: Vec<Vec<Records>> = (0..HOURS)
        .map(|h| chunks.iter_mut().map(|c| std::mem::take(&mut c[h])).collect())
        .collect();
    (order, names, Mutex::new(jobs.into_iter().enumerate()))
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
    let next_id = AtomicU32::new(0);
    // The parse threads go on to summarize: after a barrier, one of them makes the plan, and after
    // a second one all take hours from the queue.
    let parsed: Vec<Mutex<Vec<Records>>> = (0..threads).map(|_| Mutex::default()).collect();
    let plan: OnceLock<(Vec<u32>, Vec<Vec<u8>>, Jobs)> = OnceLock::new();
    let barrier = Barrier::new(threads);
    let mut f = fs::File::create(format!("{out_dir}/summary.txt")).expect("create summary.txt");
    let (tx, rx) = mpsc::channel();
    thread::scope(|s| {
        for t in 0..threads {
            let (tx, shared, next_id, parsed, plan, barrier) =
                (tx.clone(), &shared, &next_id, &parsed, &plan, &barrier);
            let (start, end) = (cuts[t], cuts[t + 1]);
            s.spawn(move || {
                *parsed[t].lock().unwrap() = parse(d, start, end, shared, next_id);
                if barrier.wait().is_leader() {
                    let _ = plan.set(make_plan(shared, parsed));
                }
                barrier.wait();
                // Workers take whole hours, in order, from a queue; the main thread writes them
                // out in order.
                let (order, names, jobs) = plan.get().unwrap();
                let mut scratch = Scratch::default();
                while let Some((h, records)) = { let job = jobs.lock().unwrap().next(); job } {
                    tx.send((h, summarize(h, records, order, names, &mut scratch))).unwrap();
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
