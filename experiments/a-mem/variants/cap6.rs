//! Speed Demon 2026, Track A (Ingest): per (hour, endpoint) count, p50/p95/p99 and 5xx rate.
//!
//! 1. mmap the log and split it into newline-aligned chunks of about 512 KiB, taken in file
//!    order by the threads.
//! 2. A thread parses a chunk into packed records (endpoint id, 5xx bit, latency), bucketed by
//!    hour. Its own endpoint table caches the dense ids (0, 1, 2, ...) handed out by shared maps
//!    (sharded by hash, to spread lock contention) that keep copies of the names, so no merge is
//!    needed and the chunk's pages can be dropped.
//! 3. The log is nearly in time order, so once every chunk up to some point is parsed, the hours
//!    before the latest hour seen there, but one, are closed: queued to be summarized while later
//!    chunks are parsed, so only a few hours of records are held at a time. A record that comes
//!    for a closed hour makes the whole run start over without closing hours early.
//! 4. Threads take queued hours before chunks, at most four at a time: sort the names seen so
//!    far (an endpoint's position in byte order is its output rank; kept until new names appear),
//!    count the hour's records per endpoint id, counting-sort its latencies into groups laid out
//!    in rank order, find the three nearest-rank percentiles (branch-free AVX2 rank counting for
//!    groups of up to 64 values, selection otherwise), format the lines and write them once the
//!    hours before are written. Record and output buffers are reused, not freed, until no chunk
//!    or hour is left.
use std::collections::{HashMap, VecDeque};
use std::sync::{atomic::{AtomicU32, Ordering}, Arc, Condvar, Mutex};
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
    // SAFETY: in bounds by the assert; AVX2 is enabled at compile time; loads are unaligned.
    unsafe {
        use std::arch::x86_64::*;
        let load = |d: &[u8], i: usize| _mm256_loadu_si256(d.as_ptr().add(i).cast());
        let other = |k: usize| b.map_or(_mm256_set1_epi8(c as i8), |(b, j)| load(b, j + k));
        let half = |k| _mm256_movemask_epi8(_mm256_cmpeq_epi8(load(a, i + k), other(k))) as u32;
        half(0) as u64 | (half(32) as u64) << 32
    }
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
    slots: Vec<u32>, // 1 + offset of the entry in `arena`, or 0 if empty
    len: usize,
    arena: Vec<u8>,
}

impl Table {
    /// Returns the shared id of endpoint `d[s..e]` (hash `h`), asking `new` for it if unseen.
    #[inline(always)]
    fn find(&mut self, d: &[u8], h: u64, s: usize, e: usize, new: impl FnOnce() -> u32) -> u32 {
        if self.slots.is_empty() {
            // The spec fixes 1,842 endpoints per seed; 4,096 slots keep the load below one half.
            self.slots = vec![0; 1 << 12];
            self.arena.reserve(1 << 17); // ample, mapped directly: no copies left in the heap by growth
        }
        let (mask, n) = (self.slots.len() - 1, e - s);
        let mut i = (h >> 40) as usize & mask;
        while self.slots[i] != 0 {
            let at = self.slots[i] as usize - 1;
            let (nh, meta) = (load(&self.arena, at), load(&self.arena, at + 8));
            if nh == h
                && meta as u32 as usize == n
                && if n < 64 {
                    !eq_mask(&self.arena, at + 16, Some((d, s)), 0) & ((1 << n) - 1) == 0
                } else {
                    // In bounds as the arena ends with 64 zero bytes; bytes past the name are masked.
                    !eq_mask(&self.arena, at + 16, Some((d, s)), 0) == 0
                        && !eq_mask(&self.arena, at + 80, Some((d, s + 64)), 0) & ((1 << (n - 64)) - 1) == 0
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
        self.len += 1;
        assert!(self.len < 2048, "more endpoints than the spec allows");
        self.slots[i] = at as u32 + 1;
        id
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
fn parse(run: &Run, mut i: usize, end: usize, table: &mut Table) -> Vec<Records> {
    let (d, shared, next_id) = (run.d, &run.shared, &run.next_id);
    let page = i & !4095;
    let mut hours = vec![(Vec::new(), Vec::new()); HOURS];
    // The current hour's records, swapped out of `hours`: consecutive lines almost always share
    // an hour, so most lines push to this local pair without indexing `hours`.
    let (mut cur_h, mut cur): (usize, Records) = (HOURS, (Vec::new(), Vec::new()));
    let mut n = 0; // length of `cur.0`, kept in a register and stored only when the hour changes
    while i < end {
        // Bytes 5..13 are "MM-DDTHH"; their low nibbles x make 10 * x[k] + x[k + 1] in byte k of
        // y without carries. October 30, 31 and November 1, 2 become day indexes 0..=3.
        let x = load(d, i + 5) & (ONES * 0x0f);
        let y = x * 10 + (x >> 8);
        let day = (y >> 24 & 0xff) + 31 * (x >> 8 & 0xff) - 30;
        let hour = (day * 24 + (y >> 48 & 0xff) - 18) as usize;
        let s = i + 29 + find_byte(load(d, i + 28), b' ');
        // The space after the endpoint, among the next 128 bytes (endpoints are at most 125).
        let mut e = s + eq_mask(d, s, None, b' ').trailing_zeros() as usize;
        if e == s + 64 {
            e += eq_mask(d, e, None, b' ').trailing_zeros() as usize;
        }
        assert!(e < s + 128, "endpoint longer than the spec allows");
        let h = hash(d, s, e - s);
        let id = table.find(d, h, s, e, || {
            let mut map = shared[(h >> 60) as usize].lock().unwrap(); // top 4 bits pick a shard
            *map.entry(d[s..e].to_vec()).or_insert_with(|| next_id.fetch_add(1, Ordering::Relaxed))
        }) as u64;
        let (latency, next) = parse_latency(d, e + 5);
        let is_5xx = (d[e + 1] == b'5') as u64;
        if hour != cur_h {
            unsafe { cur.0.set_len(n) };
            if cur_h < HOURS {
                std::mem::swap(&mut hours[cur_h], &mut cur);
            }
            std::mem::swap(&mut hours[hour], &mut cur);
            cur_h = hour;
            if cur.0.capacity() == 0 {
                // A spare buffer, else a new one, mapped directly (128 KiB), not grown in the heap.
                let spare = run.spare.lock().unwrap().pop();
                cur.0 = spare.unwrap_or(Vec::with_capacity(1 << 15));
                cur.0.clear();
            }
            n = cur.0.len();
        }
        let r = if id < 2048 && latency < 0x000f_ffff {
            ((id as u32) << 21) | ((is_5xx as u32) << 20) | latency as u32
        } else {
            cur.1.push(id << 33 | is_5xx << 32 | latency);
            u32::MAX
        };
        if n == cur.0.capacity() {
            unsafe { cur.0.set_len(n) };
            cur.0.reserve(n.max(1 << 15));
        }
        // SAFETY: n < capacity, checked above; the length is set before the vector is used.
        unsafe { cur.0.as_mut_ptr().add(n).write(r) };
        n += 1;
        i = next;
    }
    if cur_h < HOURS {
        unsafe { cur.0.set_len(n) };
        hours[cur_h] = cur;
    }
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

/// One summary's buffers, kept across hours so their pages fault in only once (and output
/// buffers are not freed, which would let record buffers come from the allocator's heap).
#[derive(Default)]
struct Scratch {
    counts: Vec<u64>, // per id: records | errors << 32
    next: Vec<u32>,   // per id: next free slot of its group in `lat`
    lat: Vec<u32>,
    out: Vec<u8>,
}

/// Formats every group of one hour from each chunk's records into `s.out`. `order[rank]` is the
/// id of the endpoint at output position `rank`, `names[rank]` its name.
fn summarize(hour: usize, chunks: &[Records], (order, names): &Plan, s: &mut Scratch) {
    let Scratch { counts, next, lat, out } = s;
    counts.clear();
    counts.resize(order.len(), 0);
    each(chunks, |id, error, _| counts[id] += 1 | (error as u64) << 32);
    // Groups are laid out in rank order, but looked up by id.
    next.resize(order.len(), 0);
    let mut total = 0;
    for &id in order {
        next[id as usize] = total;
        total += counts[id as usize] as u32;
    }
    lat.resize(total as usize + 64, 0); // `small_ranks` reads up to 64 values past a group
    each(chunks, |id, _, latency| {
        let slot = &mut next[id];
        lat[*slot as usize] = latency;
        *slot += 1;
    });
    let (day, hh) = ((18 + hour) / 24, (18 + hour) % 24);
    let (month, dd) = (10 + day / 2, [30, 31, 1, 2][day]);
    let prefix = format!("2026-{month:02}-{dd:02}T{hh:02}:00:00Z ");
    out.clear();
    out.reserve(1 << 18); // ample for one hour, mapped directly; untouched pages cost nothing
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
        let [p50, p95, p99] = match n {
            0..=8 => small_ranks::<1>(lat, at, n, r),
            9..=16 => small_ranks::<2>(lat, at, n, r),
            17..=32 => small_ranks::<4>(lat, at, n, r),
            33..=64 => small_ranks::<8>(lat, at, n, r),
            _ => select_ranks(&mut lat[at..at + n], r),
        };
        let e = counts[id] >> 32;
        let mut k = prefix.len() + name.len();
        line[prefix.len()..k].copy_from_slice(name);
        for x in [n as u64, p50 as u64, p95 as u64, p99 as u64, e, e * 1_000_000 / n as u64] {
            k = put_num(&mut line, k, x);
        }
        line[k] = b'\n';
        out.extend_from_slice(&line[..k + 1]);
    }
}

/// The endpoint id of each output rank and the names in rank order.
type Plan = (Vec<u32>, Vec<Vec<u8>>);

/// What the threads share in one run: the chunks between `cuts`, the endpoint names, the plan,
/// the parse progress, record buffers kept for reuse once summarized (freeing them would let
/// later ones come from the allocator's heap, where freed memory stays resident) and the output.
#[derive(Default)]
struct Run<'a> {
    d: &'a [u8],
    cuts: Vec<usize>,
    early: bool, // close hours before every chunk is parsed
    shared: [Shared; SHARDS],
    next_id: AtomicU32,
    plan: Mutex<Arc<Plan>>,
    state: Mutex<State>,
    wake: Condvar,
    spare: Mutex<Vec<Vec<u32>>>, // record buffers, freed instead once every chunk is taken
    out: Mutex<(usize, Option<fs::File>)>, // how many hours are written, and the file
    turn: Condvar,                         // signalled when an hour is written
}

/// The parse progress and the hours' records.
#[derive(Default)]
struct State {
    next: usize,             // the next chunk to parse
    top: Vec<Option<usize>>, // per parsed chunk: 1 + its latest hour (0 if empty)
    done: usize,             // chunks 0..done are parsed
    seen: usize,             // 1 + the latest hour in chunks 0..done
    closed: usize,           // hours 0..closed are queued or summarized
    hours: Vec<Vec<Records>>,
    jobs: VecDeque<(usize, Vec<Records>)>, // closed hours
    scratch: Vec<Scratch>, // free summary buffers; they bound how many hours are summarized at once
    late: bool,            // a record came for a closed hour
}

impl Run<'_> {
    /// The plan for every id handed out so far: the last one made, unless names were added since.
    fn plan(&self) -> Arc<Plan> {
        let mut plan = self.plan.lock().unwrap();
        let need = self.next_id.load(Ordering::Relaxed); // these ids are in the maps by now
        if (plan.0.len() as u32) < need {
            let mut names: Vec<(Vec<u8>, u32)> = Vec::new();
            for map in &self.shared {
                names.extend(map.lock().unwrap().iter().map(|(k, &v)| (k.clone(), v)));
            }
            names.retain(|e| e.1 < need); // so the ids are exactly 0..need
            names.sort_unstable();
            let order = names.iter().map(|e| e.1).collect();
            *plan = Arc::new((order, names.into_iter().map(|e| e.0).collect()));
        }
        plan.clone()
    }

    /// One thread's work: closed hours first, so their records are freed soon, else chunks.
    fn work(&self) {
        let (mut table, chunks) = (Table::default(), self.cuts.len() - 1);
        let mut st = self.state.lock().unwrap();
        loop {
            if !st.jobs.is_empty() && !st.scratch.is_empty() {
                let (h, records) = st.jobs.pop_front().unwrap();
                let mut scratch = st.scratch.pop().unwrap();
                drop(st);
                summarize(h, &records, &self.plan(), &mut scratch);
                // Hours are written in order: those before h are being summarized already.
                let mut out = self.out.lock().unwrap();
                while out.0 < h {
                    out = self.turn.wait(out).unwrap();
                }
                out.1.as_ref().unwrap().write_all(&scratch.out).unwrap();
                out.0 += 1;
                drop(out);
                self.turn.notify_all();
                st = self.state.lock().unwrap();
                if st.next < chunks {
                    let records = records.into_iter().map(|r| r.0);
                    self.spare.lock().unwrap().extend(records); // else free them
                }
                if st.closed < HOURS || !st.jobs.is_empty() {
                    st.scratch.push(scratch); // else no hour is left: free it
                }
            } else if st.next < chunks {
                let k = st.next;
                st.next += 1;
                if st.next == chunks {
                    *self.spare.lock().unwrap() = Vec::new(); // nothing is parsed any more
                }
                drop(st);
                let parsed = parse(self, self.cuts[k], self.cuts[k + 1], &mut table);
                st = self.state.lock().unwrap();
                let mut top = 0;
                for (h, r) in parsed.into_iter().enumerate() {
                    if !r.0.is_empty() {
                        (st.late, top) = (st.late || h < st.closed, h + 1);
                        st.hours[h].push(r);
                    }
                }
                st.top[k] = Some(top);
                while let Some(&Some(top)) = st.top.get(st.done) {
                    (st.seen, st.done) = (st.seen.max(top), st.done + 1);
                }
                // In the generated logs no record is more than an hour behind an earlier one
                // (shard 0 uploads each hour 5 to 10 minutes after it ends).
                let early = st.seen.saturating_sub(2) * self.early as usize;
                let limit = if st.done < chunks { early } else { HOURS };
                let s = &mut *st;
                for h in s.closed..limit {
                    s.jobs.push_back((h, std::mem::take(&mut s.hours[h])));
                }
                st.closed = st.closed.max(limit);
            } else if st.closed == HOURS {
                return;
            } else {
                st = self.wake.wait(st).unwrap();
                continue;
            }
            self.wake.notify_all();
        }
    }
}

/// Summarizes `d` into `out_dir/summary.txt` with `threads` threads over the chunks between
/// `cuts`. Returns false if `early` closed an hour too early; then the output is incomplete.
fn run(d: &[u8], cuts: Vec<usize>, threads: usize, early: bool, out_dir: &str) -> bool {
    let mut run = Run::default();
    (run.d, run.cuts, run.early) = (d, cuts, early);
    let st = run.state.get_mut().unwrap();
    (st.top, st.hours) = (vec![None; run.cuts.len() - 1], vec![Vec::new(); HOURS]);
    st.scratch = (0..6).map(|_| Scratch::default()).collect();
    let f = fs::File::create(format!("{out_dir}/summary.txt")).expect("create summary.txt");
    run.out.get_mut().unwrap().1 = Some(f);
    thread::scope(|s| (0..threads).for_each(|_| drop(s.spawn(|| run.work()))));
    !run.state.into_inner().unwrap().late
}

fn main() {
    let data_dir = env::var("SD_DATA").unwrap_or_else(|_| "/data".into());
    let out_dir = env::var("SD_OUT").unwrap_or_else(|_| "/out".into());
    let file = fs::File::open(format!("{data_dir}/requests.log")).expect("open requests.log");
    let len = file.metadata().unwrap().len() as usize;
    let d = map_file(&file, len);
    let cpus = thread::available_parallelism().map_or(1, |n| n.get());
    let threads = env::var("SD_THREADS").map_or(cpus, |t| t.parse().unwrap());
    // About 512 KiB per chunk, at least one per thread.
    let n = (len >> 19).max(threads);
    let mut cuts = vec![0];
    for t in 1..n {
        let mut at = (len * t / n).max(cuts[t - 1]);
        while at > 0 && at < len && d[at - 1] != b'\n' {
            at += 1;
        }
        cuts.push(at);
    }
    cuts.push(len);
    if !run(d, cuts.clone(), threads, true, &out_dir) {
        run(d, cuts, threads, false, &out_dir);
    }
}
