//! Speed Demon 2026, Track A (Ingest): per (hour, endpoint) count, p50/p95/p99 and 5xx rate.
//!
//! 1. mmap the log and split it into one newline-aligned chunk per thread.
//! 2. Each thread parses its chunk into packed records (endpoint id, 5xx bit, latency),
//!    bucketed by hour. A thread's own endpoint table caches the dense ids (0, 1, 2, ...) handed
//!    out by shared maps (sharded by hash, to spread lock contention) that keep copies of the
//!    names, so no merge is needed and the chunk's pages can be dropped.
//! 3. The shared names are sorted once, so every endpoint id gets its output rank.
//! 4. Threads take whole hours from a queue: counting-sort the hour's latencies by endpoint
//!    rank, select the three nearest-rank percentiles, format the lines, free the records.
use std::collections::HashMap;
use std::sync::{atomic::{AtomicU32, Ordering}, mpsc, Mutex};
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

/// Hash of the endpoint of `n` bytes at `s`, from its first, middle and last words and length.
#[inline(always)]
fn hash(d: &[u8], s: usize, n: usize) -> u64 {
    let h = if n >= 8 {
        load(d, s) ^ load(d, s + n / 2 - 4).rotate_left(21) ^ load(d, s + n - 8).rotate_left(42)
    } else {
        load(d, s) & ((1 << (8 * n)) - 1)
    };
    let h = (h ^ n as u64).wrapping_mul(MIX);
    (h ^ h >> 29).wrapping_mul(MIX)
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

/// A summary worker's buffers, kept across hours so their pages fault in only once.
#[derive(Default)]
struct Scratch {
    counts: Vec<u64>, // per id: records | errors << 32
    next: Vec<u32>,   // per id: next free slot of its group in `lat`
    lat: Vec<u32>,
}

/// Formats every group of one hour from each chunk's records, freeing them as soon as they are
/// sorted. `order[rank]` is the id of the endpoint at output position `rank`, `names[rank]` its name.
fn summarize(hour: usize, chunks: Vec<Records>, order: &[u32], names: &[&[u8]], s: &mut Scratch, mut out: Vec<u8>) -> Vec<u8> {
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
    lat.resize(total as usize, 0);
    each(&chunks, |id, _, latency| {
        let slot = &mut next[id];
        lat[*slot as usize] = latency;
        *slot += 1;
    });
    drop(chunks);
    let (day, hh) = ((18 + hour) / 24, (18 + hour) % 24);
    let (month, dd) = (10 + day / 2, [30, 31, 1, 2][day]);
    let prefix = format!("2026-{month:02}-{dd:02}T{hh:02}:00:00Z ");
    let mut line = [0u8; 512]; // prefix (21) + name (at most 125 by spec) + 6 numbers
    line[..prefix.len()].copy_from_slice(prefix.as_bytes());
    for (g, name) in names.iter().enumerate() {
        let id = order[g] as usize;
        let n = counts[id] as u32 as usize;
        if n == 0 {
            continue;
        }
        let end = next[id] as usize;
        let v = &mut lat[end - n..end];
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
        let e = counts[id] >> 32;
        if prefix.len() + name.len() + 6 * 21 + 1 > line.len() {
            // Longer than the spec allows; format it the slow way.
            out.extend_from_slice(prefix.as_bytes());
            out.extend_from_slice(name);
            for x in [n as u64, v[r50] as u64, v[r95] as u64, v[r99] as u64, e, e * 1_000_000 / n as u64] {
                out.extend_from_slice(format!(" {x}").as_bytes());
            }
            out.push(b'\n');
            continue;
        }
        let mut k = prefix.len() + name.len();
        line[prefix.len()..k].copy_from_slice(name);
        for x in [n as u64, v[r50] as u64, v[r95] as u64, v[r99] as u64, e, e * 1_000_000 / n as u64] {
            k = put_num(&mut line, k, x);
        }
        line[k] = b'\n';
        out.extend_from_slice(&line[..k + 1]);
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
    let next_id = AtomicU32::new(0);
    let mut chunks: Vec<Vec<Records>> = thread::scope(|s| {
        let hs: Vec<_> = cuts
            .windows(2)
            .map(|w| s.spawn(|| parse(d, w[0], w[1], &shared, &next_id)))
            .collect();
        hs.into_iter().map(|h| h.join().unwrap()).collect()
    });

    // An endpoint's position in byte order is its output rank.
    let shared: Vec<_> = shared.into_iter().map(|m| m.into_inner().unwrap()).collect();
    let mut names: Vec<(&[u8], u32)> = Vec::new();
    for map in &shared {
        names.extend(map.iter().map(|(name, &id)| (&name[..], id)));
    }
    names.sort_unstable();
    let order: Vec<u32> = names.iter().map(|&(_, id)| id).collect(); // ids are exactly 0..names.len()
    let names: Vec<&[u8]> = names.into_iter().map(|(n, _)| n).collect();
    let jobs: Vec<Vec<Records>> = (0..HOURS)
        .map(|h| chunks.iter_mut().map(|c| std::mem::take(&mut c[h])).collect())
        .collect();

    // Workers take whole hours, in order, from a queue; this thread writes them out in order.
    let mut f = fs::File::create(format!("{out_dir}/summary.txt")).expect("create summary.txt");
    let jobs = Mutex::new(jobs.into_iter().enumerate());
    let (tx, rx) = mpsc::channel();
    // Written output buffers come back for reuse: writing into fresh pages costs page faults.
    let spare: Mutex<Vec<Vec<u8>>> = Mutex::default();
    thread::scope(|s| {
        for _ in 0..threads.min(HOURS) {
            let (tx, jobs, order, names, spare) = (tx.clone(), &jobs, &order, &names, &spare);
            s.spawn(move || {
                let mut scratch = Scratch::default();
                while let Some((h, records)) = { let job = jobs.lock().unwrap().next(); job } {
                    let out = { let out = spare.lock().unwrap().pop(); out }
                        .unwrap_or_else(|| Vec::with_capacity(1 << 18)); // ample for one hour
                    tx.send((h, summarize(h, records, order, names, &mut scratch, out))).unwrap();
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
                let mut out = out;
                out.clear();
                spare.lock().unwrap().push(out);
            }
        }
    });
}
