//! Speed Demon 2026, Track A (Ingest): per (hour, endpoint) count, p50/p95/p99 and 5xx rate.
//!
//! 1. mmap the log and split it into one newline-aligned chunk per thread.
//! 2. Each thread parses its chunk into packed records (endpoint id, 5xx bit, latency),
//!    bucketed by hour. One shared append-only dictionary owns endpoint names and publishes
//!    dense ids with release stores; published names are immutable for all workers.
//!    The dictionary copies names, so each parsed input chunk's pages can be dropped.
//!    Each thread then hands its records to the shared per-hour lists.
//! 3. The same threads then meet at a barrier; the first to go on sorts the shared names once,
//!    so every endpoint id gets its output rank.
//! 4. The threads take whole hours in order from an atomic counter: count the hour's records per endpoint id,
//!    counting-sort its latencies into groups laid out in rank order, find the three
//!    nearest-rank percentiles (branch-free AVX2 rank counting for groups of up to 64 values,
//!    selection otherwise), format the lines, free the records. The main thread writes the
//!    hours in order.
use std::sync::{atomic::*, mpsc, Barrier, Mutex, OnceLock};
use std::{env, fs, io::Write, os::unix::io::AsRawFd, thread};

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
    // PROT_READ = 1; MAP_PRIVATE = 2, | MAP_ANONYMOUS = 0x20, | MAP_FIXED = 0x10.
    unsafe {
        let base = mmap(std::ptr::null_mut(), len + 4096, 1, 0x22, -1, 0);
        assert!(base as isize > 0, "mmap failed");
        assert!(len == 0 || mmap(base, len, 1, 0x12, file.as_raw_fd(), 0) == base);
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

/// Index of the first byte equal to `b` in the word `w`, or 8 if none: the high bit of the first
/// zero byte of `x` is set (higher bytes may be noise).
#[inline(always)]
fn find_byte(w: u64, b: u8) -> usize {
    let x = w ^ (ONES * b as u64);
    ((x.wrapping_sub(ONES) & !x & (ONES << 7)).trailing_zeros() / 8) as usize
}

/// Bit `k` is set iff `a[i + k] == b[j + k]` (`b == None`: iff `a[i + k] == c`), for `k` in 0..64.
/// Reads 64 bytes at `i` (and `j`). In the file, callers start inside a line (at an endpoint),
/// so the reads end at most 64 bytes past the last line, within the 4 KiB zero pad of
/// `map_file`; dictionary reads stay within each entry's 128-byte name.
#[inline(always)]
fn eq_mask(a: &[u8], i: usize, b: Option<(&[u8], usize)>, c: u8) -> u64 {
    assert!(i + 64 <= a.len() && b.map_or(true, |(b, j)| j + 64 <= b.len()));
    // SAFETY: in bounds by the assert; AVX2 is enabled at compile time; loads are unaligned.
    unsafe {
        use std::arch::x86_64::*;
        let load = |d: &[u8], i: usize| _mm256_loadu_si256(d.as_ptr().add(i).cast());
        let other = |k: usize| b.map_or(_mm256_set1_epi8(c as i8), |(b, j)| load(b, j + k));
        let half = |k| _mm256_movemask_epi8(_mm256_cmpeq_epi8(load(a, i + k), other(k))) as u32;
        half(0) as u64 | (half(32) as u64) << 32
    }
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

/// Append-only open addressing over 8192 slot words, each 0 or `hash & !0xfff | id + 1`; then per
/// id 16 words (128 bytes, 64-byte aligned): the name, a space and zeros, so 64-byte equality
/// loads stay inside and a short name is one cache line. The slot's release store publishes the
/// name. The counter gives out the ids (at most 2048).
type Dictionary = (&'static [AtomicU64], AtomicUsize);

/// The 128-byte name block of `id`.
fn name(dict: &[AtomicU64], id: usize) -> &[u8] {
    // SAFETY: 16 words in bounds; written only before the slot that publishes `id`.
    unsafe { std::slice::from_raw_parts(dict[8192 + 16 * id..][..16].as_ptr().cast(), 128) }
}

/// The id of the endpoint `d[s..e]`, adding it to the dictionary if it is new. The hash comes
/// from the endpoint's first and last words and its length.
#[inline(always)]
fn find((dict, next): &Dictionary, d: &[u8], s: usize, e: usize) -> u32 {
    let n = e - s;
    let h = if n >= 8 {
        load(d, s) ^ load(d, e - 8).rotate_left(29)
    } else {
        load(d, s) & ((1 << (8 * n)) - 1)
    };
    let h = (h ^ n as u64).wrapping_mul(0x9E37_79B9_7F4A_7C15) & !0xfff;
    let mut i = (h >> 40) as usize;
    loop {
        let slot = &dict[i & 8191];
        let mut v = slot.load(Ordering::Acquire);
        // An empty slot is claimed with 0xfff (no id), then filled; a racing thread waits.
        if v == 0 && slot.compare_exchange(0, 0xfff, Ordering::Relaxed, Ordering::Relaxed).is_ok() {
            let id = next.fetch_add(1, Ordering::Relaxed);
            assert!(id < 2048, "more endpoints than the spec allows");
            let p = dict[8192 + 16 * id].as_ptr().cast::<u8>();
            // SAFETY: n < 128, the block is new, and the release store below publishes it.
            unsafe { p.copy_from_nonoverlapping(d[s..e].as_ptr(), n) };
            unsafe { p.add(n).write(b' ') };
            v = h | (id + 1) as u64;
            slot.store(v, Ordering::Release);
        }
        while v & 0xfff == 0xfff || v == 0 {
            v = slot.load(Ordering::Acquire);
        }
        // Equal through the space: the same name, and the stored one is no longer. Both 64-byte
        // halves are always compared, so the endpoint's length costs no mispredicted branch.
        let id = (v & 0xfff) as usize - 1;
        let diff = |k: usize| !eq_mask(name(dict, id), k, Some((d, s + k)), 0) as u128;
        if v & !0xfff == h && (diff(0) | diff(64) << 64) & ((2 << n) - 1) == 0 {
            return id as u32;
        }
        i += 1;
    }
}

/// One chunk's records of one hour: `id << 21 | is_5xx << 20 | latency`, or `u32::MAX` for the
/// next escaped record `id << 33 | is_5xx << 32 | latency`.
type Records = (Vec<u32>, Vec<u64>);

/// Parses the lines in `d[i..end]` into records per hour using the shared dictionary.
fn parse(d: &[u8], mut i: usize, end: usize, shared: &Dictionary) -> Vec<Records> {
    let page = i & !4095;
    // One extra slot parks the empty pair that `cur` starts as.
    let mut hours = vec![(Vec::new(), Vec::new()); HOURS + 1];
    // The current hour's records, swapped out of `hours`: consecutive lines almost always share
    // an hour, so most lines push to this local pair without indexing `hours`.
    // `n` is the length of `cur.0`, kept in a register and stored only when the hour changes.
    // `key` is bytes 5..13 of the current hour's lines, "MM-DDTHH": compared, not parsed.
    let (mut cur_h, mut cur, mut n, mut cur_key) = (HOURS, Records::default(), 0, 0);
    while i < end {
        let key = load(d, i + 5);
        let s = i + 29 + find_byte(load(d, i + 28), b' ');
        // The space after the endpoint, among the next 128 bytes (endpoints are at most 125).
        let mut e = s + eq_mask(d, s, None, b' ').trailing_zeros() as usize;
        if e == s + 64 {
            e += eq_mask(d, e, None, b' ').trailing_zeros() as usize;
        }
        assert!(e < s + 128, "endpoint longer than the spec allows");
        let id = find(shared, d, s, e) as u64;
        let (latency, next) = parse_latency(d, e + 5);
        let is_5xx = (d[e + 1] == b'5') as u64;
        if key != cur_key {
            // The low nibbles x of "MM-DDTHH" make 10 * x[k] + x[k + 1] in byte k of y without
            // carries. October 30, 31 and November 1, 2 become day indexes 0..=3.
            let x = key & (ONES * 0x0f);
            let y = x * 10 + (x >> 8);
            let day = (y >> 24 & 0xff) + 31 * (x >> 8 & 0xff) - 30;
            let hour = (day * 24 + (y >> 48 & 0xff) - 18) as usize;
            cur_key = key;
            unsafe { cur.0.set_len(n) };
            std::mem::swap(&mut hours[cur_h], &mut cur);
            std::mem::swap(&mut hours[hour], &mut cur);
            (cur_h, n) = (hour, cur.0.len());
        }
        let r = if latency < 0x000f_ffff {
            ((id as u32) << 21) | ((is_5xx as u32) << 20) | latency as u32
        } else {
            cur.1.push(id << 33 | is_5xx << 32 | latency);
            u32::MAX
        };
        if n == cur.0.capacity() {
            unsafe { cur.0.set_len(n) };
            // A new vector gets 128 KiB, mapped directly, not grown through the allocator's heap.
            cur.0.reserve(n.max(1 << 15));
        }
        // SAFETY: n < capacity, checked above; the length is set before the vector is used.
        unsafe { cur.0.as_mut_ptr().add(n).write(r) };
        n += 1;
        i = next;
    }
    unsafe { cur.0.set_len(n) };
    hours[cur_h] = cur;
    // Drop this chunk's file pages from the mapping now, in parallel, instead of at exit on one
    // thread. Nothing reads these pages again (a read would fault the file back in).
    unsafe { madvise(d.as_ptr().add(page), end - page, 4) }; // MADV_DONTNEED
    hours
}

/// Writes " " and the decimal digits of `v` at `b[at..]`; returns the index past them.
#[inline(always)]
fn put_num(b: &mut [u8], at: usize, mut v: u64) -> usize {
    b[at] = b' ';
    let end = at + 2 + v.checked_ilog10().unwrap_or(0) as usize;
    for i in (at + 1..end).rev() {
        b[i] = b'0' + (v % 10) as u8;
        v /= 10;
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
    // Each selection leaves larger values to the right, so later ones search less.
    v.select_nth_unstable(r50);
    if r95 > r50 {
        v[r50 + 1..].select_nth_unstable(r95 - r50 - 1);
    }
    if r99 > r95 {
        v[r95 + 1..].select_nth_unstable(r99 - r95 - 1);
    }
    [v[r50], v[r95], v[r99]]
}

/// A summary worker's buffers, kept across hours so their pages fault in only once: per id
/// records | errors << 32, per id the next free slot of its group in the latencies, latencies.
type Scratch = (Vec<u64>, Vec<u32>, Vec<u32>);

/// The endpoint names in rank (byte) order, and the id of each rank.
type Plan<'a> = (Vec<&'a [u8]>, Vec<u32>);

/// Formats every group of one hour from each chunk's records into `out`, freeing the records as
/// soon as they are sorted.
fn summarize(hour: usize, chunks: Vec<Records>, plan: &Plan, s: &mut Scratch, out: &mut Vec<u8>) {
    let ((names, order), (counts, next, lat)) = (plan, s);
    *counts = vec![0; order.len()];
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
    out.clear();
    out.reserve(1 << 18);
    let mut line = [0u8; 512]; // prefix (21) + name (at most 125 by spec) + 6 numbers
    line[..prefix.len()].copy_from_slice(prefix.as_bytes());
    for (g, name) in names.iter().enumerate() {
        let id = order[g] as usize;
        let n = counts[id] as u32 as usize;
        if n == 0 {
            continue;
        }
        let at = next[id] as usize - n;
        let r = [50, 95, 99].map(|p| (p * n + 99) / 100 - 1);
        let [p50, p95, p99] = match n {
            0..=8 => small_ranks::<1>(lat, at, n, r),
            9..=16 => small_ranks::<2>(lat, at, n, r),
            17..=32 => small_ranks::<4>(lat, at, n, r),
            33..=64 => small_ranks::<8>(lat, at, n, r),
            _ => select_ranks(&mut lat[at..at + n], r),
        }
        .map(u64::from);
        let e = counts[id] >> 32;
        let mut k = prefix.len() + name.len();
        line[prefix.len()..k].copy_from_slice(name);
        for x in [n as u64, p50, p95, p99, e, e * 1_000_000 / n as u64] {
            k = put_num(&mut line, k, x);
        }
        line[k] = b'\n';
        out.extend_from_slice(&line[..k + 1]);
    }
}

/// Sorts the endpoint names once every chunk is parsed: an endpoint's position in byte order is
/// its output rank. The ids are exactly 0..names.len().
fn make_plan((dict, next): &Dictionary) -> Plan<'_> {
    let name = |id| name(dict, id).split(|&c| c == b' ').next().unwrap();
    let mut names: Vec<_> = (0..next.load(Ordering::Relaxed)).map(|id| (name(id), id as u32)).collect();
    names.sort_unstable();
    names.into_iter().unzip()
}

fn main() {
    let data_dir = env::var("SD_DATA").unwrap_or_else(|_| "/data".into());
    let out_dir = env::var("SD_OUT").unwrap_or_else(|_| "/out".into());
    let file = fs::File::open(format!("{data_dir}/requests.log")).expect("open requests.log");
    let len = file.metadata().unwrap().len() as usize;
    let d = map_file(&file, len);
    let cpus = thread::available_parallelism().map_or(1, |n| n.get());
    let threads = env::var("SD_THREADS").map_or(cpus, |t| t.parse().unwrap());

    // Chunk t starts at the first line start at or after len * t / threads (so cuts never decrease).
    let cut = |t: usize| {
        let mut at = len * t / threads;
        while at > 0 && at < len && d[at - 1] != b'\n' {
            at += 1;
        }
        at
    };
    // 8192 slots and 2048 names of 16 words, as zero pages (read | write, private | anonymous).
    let words = unsafe { mmap(std::ptr::null_mut(), (8192 + 2048 * 16) * 8, 3, 0x22, -1, 0) };
    assert!(words as isize > 0, "mmap failed");
    let shared = &(unsafe { std::slice::from_raw_parts(words.cast(), 8192 + 2048 * 16) }, AtomicUsize::new(0));
    // Each hour's records, one entry per chunk. The parse threads go on to summarize: after a
    // barrier, the first to need the plan makes it, and all take hours in order from a counter.
    let hours: &Vec<Mutex<Vec<Records>>> = &(0..HOURS).map(|_| Mutex::default()).collect();
    let (plan, next_hour) = (&OnceLock::new(), &AtomicUsize::new(0));
    let barrier = &Barrier::new(threads);
    let mut f = fs::File::create(format!("{out_dir}/summary.txt")).expect("create summary.txt");
    let (tx, rx) = mpsc::channel();
    let pool = &Mutex::new(Vec::<Vec<u8>>::new());
    thread::scope(|s| {
        for t in 0..threads {
            let tx = tx.clone();
            s.spawn(move || {
                for (hour, r) in hours.iter().zip(parse(d, cut(t), cut(t + 1), shared)) {
                    hour.lock().unwrap().push(r);
                }
                barrier.wait();
                // The main thread writes the hours out in order.
                if threads > 1 && t == threads - 1 {
                    return;
                }
                let plan = plan.get_or_init(|| make_plan(shared));
                let mut scratch = Scratch::default();
                while let h @ 0..HOURS = next_hour.fetch_add(1, Ordering::Relaxed) {
                    let chunks = std::mem::take(&mut *hours[h].lock().unwrap());
                    let mut out = pool.lock().unwrap().pop().unwrap_or_default();
                    summarize(h, chunks, plan, &mut scratch, &mut out);
                    tx.send((h, out)).unwrap();
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
                let mut pool = pool.lock().unwrap();
                if pool.len() < 4 { pool.push(out); }
            }
        }
    });
}
