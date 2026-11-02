//! Speed Demon 2026, Track C (Join): std-only Rust. README.md explains the design.
use std::arch::x86_64::*;
use std::sync::atomic::{AtomicBool, AtomicU64, AtomicU8, AtomicUsize, Ordering::*};
use std::{env, fs, os::fd::AsRawFd, os::unix::fs::FileExt, sync::Barrier, sync::Mutex, thread};

extern "C" {
    fn mmap(addr: *mut u8, len: usize, prot: i32, flags: i32, fd: i32, off: i64) -> *mut u8;
    fn madvise(addr: *mut u8, len: usize, advice: i32) -> i32;
    fn mallopt(param: i32, value: i32) -> i32;
}

/// Maps a file read-only (PROT_READ, MAP_PRIVATE): its pages stay in the shared page cache.
/// An anonymous page follows it, so 64 bytes past its end can be read.
fn map(path: String) -> &'static [u8] {
    let f = fs::File::open(&path).expect(&path);
    let len = f.metadata().unwrap().len() as usize;
    unsafe {
        let p = mmap(0 as _, len + 4096, 1, 0x22, -1, 0);
        assert!(mmap(p, len, 1, 0x12, f.as_raw_fd(), 0) == p); // MAP_FIXED over its start
        std::slice::from_raw_parts(p, len)
    }
}

/// `n` zeroed atomics from an anonymous map without huge pages (MADV_NOHUGEPAGE). Each thread
/// faults in the 4 KiB pages it writes; threads that fault one empty huge page at the same
/// time each allocate and charge one, which raises the measured peak memory.
fn zeroed<T>(n: usize) -> &'static [T] {
    let len = n * std::mem::size_of::<T>();
    unsafe {
        let p = mmap(0 as _, len, 3, 0x22, -1, 0);
        madvise(p, len, 15);
        std::slice::from_raw_parts(p as _, n)
    }
}

/// Asks the CPU to start loading the cache line at `p` without waiting.
fn prefetch<T>(p: &T) {
    unsafe { _mm_prefetch::<_MM_HINT_T0>(p as *const T as _) };
}

/// Bytes `p..p + 8` of `b` as a little-endian word. Callers only read where eight bytes
/// exist: each number ends at least eight bytes into its buffer.
fn ld(b: &[u8], p: usize) -> u64 {
    unsafe { (b.as_ptr().add(p) as *const u64).read_unaligned() }
}

/// The low `n` bits of `x` (all of them when n >= 64).
fn low(x: u64, n: u32) -> u64 {
    unsafe { _bzhi_u64(x, n) }
}

/// Bit i is set where b[p + i] == c, for 64 bytes. Callers only read where 64 bytes exist.
fn eq64(b: &[u8], p: usize, c: u8) -> u64 {
    unsafe {
        let (p, c) = (b.as_ptr().add(p) as *const _, _mm256_set1_epi8(c as i8));
        let eq = |p| _mm256_movemask_epi8(_mm256_cmpeq_epi8(_mm256_loadu_si256(p), c));
        eq(p) as u32 as u64 | (eq(p.add(1)) as u32 as u64) << 32
    }
}

/// Bits 8k..8k + 8 are set where the k-th of the eight words from w is y.
fn eq8(w: &AtomicU64, y: u64) -> u64 {
    unsafe {
        let (p, y) = (w as *const _ as *const __m256i, _mm256_set1_epi64x(y as _));
        let eq = |p| _mm256_movemask_epi8(_mm256_cmpeq_epi64(_mm256_loadu_si256(p), y));
        eq(p) as u32 as u64 | (eq(p.add(1)) as u32 as u64) << 32
    }
}

/// The number whose decimal digits fill the top `n` (1 to 8) bytes of `x`, eight at once.
fn num(x: u64, n: usize) -> u64 {
    let v = (x & 0x0F0F0F0F0F0F0F0F & !0 << (64 - 8 * n)).wrapping_mul(2561) >> 8;
    let v = (v & 0x00FF00FF00FF00FF).wrapping_mul(6553601) >> 16;
    (v & 0x0000FFFF0000FFFF).wrapping_mul(42949672960001) >> 32
}

/// 16 bytes from `p` (anything that big) as a vector.
fn at16<T>(p: &T) -> __m128i {
    unsafe { _mm_loadu_si128(p as *const T as _) }
}
const ONE100: __m256i = unsafe { std::mem::transmute([0x1_0064u32; 8]) }; // pairs (100, 1)

/// Bit i is the XOR of bits 0..=i of x: set inside quotes, given x's quote positions.
fn prefix_xor(x: u64) -> u64 {
    unsafe {
        let p = _mm_clmulepi64_si128(_mm_set_epi64x(0, x as i64), _mm_set1_epi8(-1), 0);
        _mm_cvtsi128_si64(p) as u64
    }
}

/// The 64-bit hash of the name `b[s..e]`. Names are identified by 56 bits of it, not
/// compared byte for byte: two of the ~10^5 names in one owner's table share them with
/// probability ~7e-8. Each 32 bytes of the name, zero padded (names never contain a zero
/// byte), go through an AES round, the two halves as data and round key; two more rounds
/// mix the last ones in, and the 128-bit state is folded in half. (With one round after the
/// data instead of two, the folded top bits of names of one length collide three times too
/// often.)
fn name_hash(b: &[u8], s: usize, e: usize) -> u64 {
    unsafe {
        let (mut h, mut o) = (_mm_set_epi64x(K as i64, !K as i64), s);
        loop {
            let v = _mm256_loadu_si256(b.as_ptr().add(o) as _);
            let n = _mm256_set1_epi8((e - o).min(32) as i8); // keep bytes j < n
            let keep = _mm256_cmpgt_epi8(n, _mm256_loadu_si256(IOTA.as_ptr() as _));
            let v = _mm256_and_si256(v, keep);
            let (lo, hi) = (_mm256_castsi256_si128(v), _mm256_extracti128_si256::<1>(v));
            (h, o) = (_mm_aesenc_si128(_mm_xor_si128(h, lo), hi), o + 32);
            if o >= e {
                break; // over 32 bytes: rare
            }
        }
        let h = _mm_aesenc_si128(h, _mm_set1_epi64x(K as _));
        let h = _mm_aesenc_si128(h, _mm_set1_epi8(1));
        (_mm_cvtsi128_si64(h) ^ _mm_extract_epi64::<1>(h)) as u64
    }
}
const IOTA: [i8; 32] = [
    0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25,
    26, 27, 28, 29, 30, 31,
];
const K: u64 = 0x517cc1b727220a95; // FxHash's multiplier

/// A value on its own pair of cache lines.
#[derive(Default)]
#[repr(align(128))]
struct Pad<T>(T);
const BATCH: usize = 64;
const BLOCK: usize = 512;

/// The ends of the id and the name, the first two commas outside quotes from the record's
/// start at b[s..], and the quotes in the name.
fn fields(b: &[u8], s: usize) -> (usize, usize, usize) {
    let q = eq64(b, s, b'"');
    let e = eq64(b, s, b',') & !prefix_xor(q);
    let (f0, e1) = (s + e.trailing_zeros() as usize, e & (e - 1));
    if e1 == 0 {
        let (f1, nq) = field_end(b, f0 + 1); // a name past the 64 bytes: rare
        return (f0, f1, nq);
    }
    let t = e1.trailing_zeros();
    (f0, s + t as usize, low(q, t).count_ones() as usize)
}

/// Where the field at b[s..] ends (the first comma outside quotes) and the quotes before it.
fn field_end(b: &[u8], mut s: usize) -> (usize, usize) {
    let (mut open, mut quotes) = (0, 0);
    loop {
        let q = eq64(b, s, b'"');
        let inside = prefix_xor(q) ^ open;
        let e = eq64(b, s, b',') & !inside;
        if e != 0 {
            let t = e.trailing_zeros();
            return (s + t as usize, quotes + low(q, t).count_ones() as usize);
        }
        open = (inside as i64 >> 63) as u64;
        (quotes, s) = (quotes + q.count_ones() as usize, s + 64);
    }
}

/// What a record adds to its group's totals, and its region and name hash.
#[derive(Clone, Copy, Default)]
struct Rec {
    h: u64,
    rid: u32,
    id: u32,
    cents: i32,
    nl: u32,
    tl: u32,
}

/// pshufb masks for the 16 bytes that end where a record's amount ends: entry 8a + r moves a
/// region id of r digits to bytes 0..8 and an amount of a bytes ([-]d+.dd, '.' dropped) to
/// bytes 8..16, both right-aligned. 0x80 zeroes a byte.
const SPLIT: [[u8; 16]; 72] = {
    let (mut t, mut i) = ([[0x80; 16]; 72], 0);
    while i < 72 * 16 {
        let (a, r, j) = (i / 128, i / 16 % 8, i % 16);
        if j < 8 && 7 - j < r && a < 8 + j {
            t[i / 16][j] = (7 + j - a) as u8; // the region's digits end at 14 - a
        } else if j > 13 || j > 7 && 16 - j < a {
            t[i / 16][j] = (j - (j < 14) as usize) as u8; // the amount's, around the '.' at 13
        }
        i += 1;
    }
    t
};

/// The record b[rs..=p] ([BOM] id , name , note , region , amount [CR] LF) holding `quotes`
/// quotes, all in its name and note. Its numbers are decoded at once from the 16 bytes that
/// end with the id and the 16 that end with the amount: ids have at most 8 digits, regions 7,
/// and an amount (-999.99 to 99999.99) at most 8 bytes, so the region's comma is the window's
/// second last comma, or the byte before it (spec 2.2).
fn record(b: &[u8], rs: usize, p: usize, quotes: usize) -> Rec {
    let i = rs + 3 * (ld(b, rs) as u8 == 0xEF) as usize; // a byte order mark
    let (f0, f1, nq) = fields(b, rs);
    let ae = p - (ld(b, p - 8) >> 56 == b'\r' as u64) as usize;
    let at = |p: usize| unsafe { _mm_loadu_si128(b.as_ptr().add(p) as _) };
    let tail = at(ae - 16);
    let cm = unsafe { _mm_movemask_epi8(_mm_cmpeq_epi8(tail, _mm_set1_epi8(b',' as i8))) } as u32;
    // The window holds the amount's comma f3 = ae - 16 + (31 - z3) and the region's comma
    // f2 = ae - 16 + (31 - z2), or f2 = ae - 17 when z2 = 32.
    let z3 = cm.leading_zeros() as usize;
    let z2 = (cm ^ 1 << (31 - z3)).leading_zeros() as usize;
    let (f2, f3) = (ae + 15 - z2, ae + 15 - z3);
    let v = unsafe {
        // Entry 8a + r, for the amount's a = z3 - 16 bytes and the region's r = z2 - z3 - 1.
        let split = at16(SPLIT.get_unchecked(7 * z3 + z2 - 129));
        let keep = _mm_cmpgt_epi8(at16(&IOTA), _mm_set1_epi8((15 + i - f0) as i8)); // f0 - i
        let id = _mm_and_si128(at(f0 - 16), keep);
        let v = _mm256_set_m128i(id, _mm_shuffle_epi8(tail, split));
        let v = _mm256_subs_epu8(v, _mm256_set1_epi8(b'0' as i8));
        let v = _mm256_madd_epi16(_mm256_maddubs_epi16(v, _mm256_set1_epi16(0x010A)), ONE100);
        let v = _mm256_madd_epi16(_mm256_packus_epi32(v, v), _mm256_set1_epi32(0x1_2710));
        std::mem::transmute::<_, [u64; 4]>(v)
    };
    // A quoted field has 2 + 2k quotes for k "" escapes, and 2 + k bytes fewer.
    let len = |raw: usize, q: usize| (raw - q / 2 - (q > 0) as usize) as u32;
    let quoted = (nq > 0) as usize;
    let sign = 1 - 2 * (ld(b, f3 + 1) as u8 == b'-') as i32;
    Rec {
        h: name_hash(b, f0 + 1 + quoted, f1 - quoted),
        rid: v[0] as u32,
        id: (v[2] >> 32) as u32,
        cents: sign * (v[0] >> 32) as i32,
        nl: len(f1 - f0 - 1, nq),
        tl: len(f2 - f1 - 1, quotes - nq),
    }
}

/// Calls f(id, country) for the lines `id,CCC` of r[p..e] (p and e start lines, and 64 bytes
/// past e can be read), the country as a number from 1 to 26^3. Each comma is 4 bytes before
/// its line's LF.
fn regions(r: &[u8], p: usize, e: usize, mut f: impl FnMut(usize, usize)) {
    let mut s = p; // the line's start
    for base in (p..e).step_by(64) {
        let mut lf = low(eq64(r, base, b'\n'), (e - base).min(64) as u32);
        while lf != 0 {
            let q = base + lf.trailing_zeros() as usize;
            let c = (ld(r, q - 8) >> 40) as usize;
            let code = (c & 255) * 676 + (c >> 8 & 255) * 26 + (c >> 16) - 65 * 703 + 1;
            f(num(ld(r, q - 12), q - 4 - s) as usize, code);
            (s, lf) = (q + 1, lf & (lf - 1));
        }
    }
}

/// One output line: count id_sum amount_sum amount_min amount_max names_distinct name_bytes note_bytes.
type Agg = [i64; 8];
const EMPTY: Agg = [0, 0, 0, i64::MAX, i64::MIN, 0, 0, 0];

fn merge(a: &mut Agg, b: Agg) {
    for i in 0..8 {
        a[i] = match i {
            3 => a[i].min(b[i]),
            4 => a[i].max(b[i]),
            _ => a[i] + b[i],
        };
    }
}

/// Column `i` of an output line: integer cents print as money, the rest as plain integers.
fn column(i: usize, v: i64) -> String {
    let (sign, a) = (if v < 0 { "-" } else { "" }, v.unsigned_abs());
    match i {
        2..=4 => format!(" {sign}{}.{:02}", a / 100, a % 100),
        _ => format!(" {v}"),
    }
}

/// Writes the lines in key order: the countries by code, then _UNMATCHED (code 0).
fn report(aggs: &[Agg; 256], group: &[AtomicU8], out: &str) {
    let mut text = String::new();
    for c in (1..17577).chain([0]) {
        let g = group[c].load(Relaxed) as usize;
        if (g > 0 || c == 0) && aggs[g][0] > 0 {
            let d = |k| (b'A' + ((c + 17575) / k % 26) as u8) as char;
            let key = [format!("{}{}{}", d(676), d(26), d(1)), "_UNMATCHED".into()];
            text += &key[(c == 0) as usize];
            text.extend(aggs[g].iter().enumerate().map(|(i, &v)| column(i, v)));
            text.push('\n');
        }
    }
    fs::create_dir_all(out).unwrap();
    fs::write(format!("{out}/aggregates.txt"), text).unwrap();
}

fn main() {
    unsafe { mallopt(-8, 1) }; // one malloc arena (M_ARENA_MAX): blocks freed by owners are reused by all
    let dir = |k, d: &str| env::var(k).unwrap_or(d.into());
    let (data, out) = (dir("SD_DATA", "/data"), dir("SD_OUT", "/out"));
    let file = fs::File::open(format!("{data}/records.csv")).expect("records.csv");
    let size = file.metadata().unwrap().len() as usize;
    let regs = map(format!("{data}/regions.csv"));
    let n = thread::available_parallelism().map_or(1, |n| n.get());
    // regions.csv is sorted, so its last line holds the largest region id.
    let last = regs[..regs.len() - 1].iter().rposition(|&c| c == b'\n');
    let mut max = 0;
    regions(regs, last.unwrap() + 1, regs.len(), |id, _| max = id);
    // One spare entry past the largest id, never written: ids above it read it as group 0.
    let region: &[AtomicU8] = zeroed(max + 2);
    // Each country's group, numbered from 1 in the order the threads first meet them; 0 until then.
    let group: Vec<AtomicU8> = (0..17577).map(|_| AtomicU8::new(0)).collect();
    let groups = Mutex::new(0u8);
    // Records are cut into 16 chunks per thread, each moved to start after a CRLF: CR only
    // ever occurs in a record terminator (spec 2.2), so a chunk starts outside quotes. The
    // chunks shrink towards the end of the file, so the threads finish together.
    // The first CR at or after `p` (or the file size), read 512 bytes at a time.
    let cr = |mut p: usize| loop {
        let mut b = [0; 512];
        let got = file.read_at(&mut b, p as u64).unwrap();
        match b[..got].iter().position(|&c| c == b'\r') {
            Some(i) => break p + i,
            None if got == 0 => break size,
            None => p += got,
        }
    };
    let start = cr(0) + 2; // the header ends with CRLF (spec 2.2)
    let chunks = 16 * n;
    let bound = |c: usize| match c {
        0 => start,
        _ if c == chunks => size,
        _ => (cr(size - (size - start) * (chunks - c).pow(2) / chunks.pow(2)) + 2).min(size),
    };
    let rstart = regs.iter().position(|&c| c == b'\n').unwrap() + 1;
    let rcut = |t: usize| match t {
        0 => rstart,
        _ if t == n => regs.len(),
        _ => (rstart + (regs.len() - rstart) * t / n..regs.len())
            .find(|&i| regs[i - 1] == b'\n')
            .unwrap_or(regs.len()),
    };
    // 15 * 2^13 slots in all (~100,000 names fill ~81%, spec 2.2); twice as many whenever
    // one owner's fill 7/8, which at 12 threads is ~7 standard deviations above the mean.
    let mut slots = 15 << 13;
    loop {
        // Names are split between the threads by hash. Thread o owns buckets o * m..(o + 1) * m
        // of `table`, 40 words each: eight names' keys, then for w = 0..4 word w of their
        // 256-bit sets of the groups they occur in. Other threads hand it (name, group) events
        // in blocks of BLOCK through its inbox, so only the owner reads or writes its buckets.
        let m = slots / (8 * n) + 1;
        let table: &[AtomicU64] = zeroed(40 * m * n);
        let (full, next) = (&zeroed::<AtomicBool>(1)[0], &zeroed::<AtomicUsize>(1)[0]);
        let inbox: Vec<Pad<Mutex<Vec<Vec<u64>>>>> = (0..n).map(|_| Default::default()).collect();
        let (barrier, total) = (Barrier::new(n), Mutex::new([EMPTY; 256]));
        // Worker t's share of the run: whether the run must start over with a larger table.
        let work = |t: usize| {
            // Copies of what the hot loops read, so no worker reads a line another one writes.
            let (region, inbox, n, m) = (region, &inbox[..], n, m);
            let lim = region.len() - 1;
            barrier.wait(); // all threads started: their page faults would slow the starting
            let mine = &table[40 * m * t..40 * m * (t + 1)];
            // Fault this owner's pages in now, before other threads start sending it events.
            mine.iter().step_by(512).for_each(|w| w.store(0, Relaxed));
            let mut used = 0;
            // Every thread maps its share of the region ids to their countries' groups. Group 0
            // (no country) is _UNMATCHED.
            regions(regs, rcut(t), rcut(t + 1), |id, c| {
                if group[c].load(Relaxed) == 0 {
                    let mut last = groups.lock().unwrap(); // a new country, or one just numbered
                    if group[c].load(Relaxed) == 0 {
                        *last = last.checked_add(1).expect("at most 255 countries");
                        group[c].store(*last, Relaxed);
                    }
                }
                region[id].store(group[c].load(Relaxed), Relaxed);
            });
            barrier.wait();
            let mut agg = [EMPTY; 256];
            let mut out: Vec<Vec<u64>> = vec![Vec::with_capacity(BLOCK); n];
            // An event is the name's hash with its low byte replaced by the group.
            let owner = move |x: u64| ((x >> 32) * n as u64 >> 32) as usize;
            let home = move |x: u64| ((x >> 8 & 0xFF_FFFF) * m as u64 >> 24) as usize;
            // Word w of this owner's buckets, for w < 40m.
            let word = move |w: usize| unsafe { mine.get_unchecked(w) };
            // Bits 8k..8k + 8 are set where key k of bucket b (< m) is y.
            let find = move |b: usize, y: u64| eq8(word(40 * b), y);
            let mut mark = move |agg: &mut [Agg; 256]| {
                let blocks = std::mem::take(&mut *inbox[t].0.lock().unwrap()); // unlock before the loop
                for v in blocks {
                    if used + v.len() >= 8 * m {
                        full.store(true, Relaxed); // the table might fill: start over, larger
                        continue;
                    }
                    for (j, &x) in v.iter().enumerate() {
                        let y = *unsafe { v.get_unchecked((j + 8).min(v.len() - 1)) };
                        prefetch(word(40 * home(y)));
                        prefetch(word(40 * home(y) + 8 + (y & 255) as usize / 64 * 8));
                        let (key, g, mut b) = (x | 0xFF, (x & 255) as usize, home(x));
                        // Keys fill a bucket from the front and are never removed, so a key is
                        // either in the first bucket from its home with a free slot, or absent.
                        let k = loop {
                            let hit = find(b, key);
                            if hit != 0 {
                                break hit.trailing_zeros() as usize / 8;
                            }
                            let free = find(b, 0);
                            if free != 0 {
                                let k = free.trailing_zeros() as usize / 8;
                                word(40 * b + k).store(key, Relaxed);
                                used += 1;
                                if used > 7 * m {
                                    full.store(true, Relaxed);
                                }
                                break k;
                            }
                            b = if b + 1 == m { 0 } else { b + 1 };
                        };
                        let (w, bit) = (word(40 * b + 8 + g / 64 * 8 + k), 1 << (g % 64));
                        let old = w.load(Relaxed);
                        w.store(old | bit, Relaxed);
                        agg[g][5] += (old & bit == 0) as i64;
                    }
                }
            };
            // Records are parsed into a batch and finished (group looked up, totals added, name
            // event sent) when it fills, so the region entries prefetched meanwhile have arrived.
            let (mut batch, mut nb) = ([Rec::default(); BATCH], 0);
            // The region entry for id r, or the spare entry past the end (group 0).
            let entry = move |r: u32| unsafe { region.get_unchecked((r as usize).min(lim)) };
            let flush = move |recs: &[Rec], agg: &mut [Agg; 256], out: &mut Vec<Vec<u64>>| {
                for r in recs {
                    let g = entry(r.rid).load(Relaxed);
                    let (id, c, nl, tl) = (r.id as i64, r.cents as i64, r.nl as i64, r.tl as i64);
                    merge(&mut agg[g as usize], [1, id, c, c, c, 0, nl, tl]);
                    let o = unsafe { out.get_unchecked_mut(owner(r.h)) }; // owner(h) < n = out.len()
                    o.push(r.h & !0xFF | g as u64);
                    if o.len() == BLOCK {
                        let full = std::mem::replace(o, Vec::with_capacity(BLOCK));
                        inbox[owner(r.h)].0.lock().unwrap().push(full);
                    }
                }
            };
            let claim = || Some(next.fetch_add(1, Relaxed)).filter(|&c| c < chunks);
            // The chunk is read through buf, which holds the file from offset `off`: when the
            // parse reaches its end, the unfinished record and the 32 bytes before it (read by
            // the record's windows) move to the front and the rest is refilled.
            let mut buf = vec![0u8; (1 << 15) + 64];
            while let Some(c) = claim() {
                let (begin, end) = (bound(c), bound(c + 1));
                if begin == end {
                    continue; // the last chunks can be empty
                }
                let (mut off, mut filled) = (begin - 32, 0);
                // base: the next block; rs: the record's start; qs and qr: quotes before them;
                // open: all ones when base is inside quotes.
                let (mut base, mut rs, mut qs, mut qr, mut open) = (32, 32, 0, 0, 0);
                loop {
                    let want = (end - off).min(buf.len() - 64);
                    while filled < want {
                        let got = file.read_at(&mut buf[filled..want], (off + filled) as u64);
                        filled += got.ok().filter(|&g| g > 0).expect("records.csv shrank");
                    }
                    let done = off + filled == end;
                    // A file whose last record lacks its LF gets one (there are 32 bytes before).
                    let ce = end - off + (done && end == size && buf[filled - 1] != b'\n') as usize;
                    buf[filled] = b'\n';
                    let b = &buf[..];
                    while base < if done { ce } else { filled - 63 } {
                        // A record ends at the first LF outside quotes.
                        let quote = eq64(b, base, b'"');
                        let inside = prefix_xor(quote) ^ open;
                        let mut ends = eq64(b, base, b'\n') & !inside;
                        if base + 64 > ce {
                            ends = low(ends, (ce - base) as u32); // the chunk's end
                        }
                        open = (inside as i64 >> 63) as u64;
                        while ends != 0 {
                            let z = ends.trailing_zeros();
                            ends &= ends - 1;
                            let p = base + z as usize;
                            let qp = qs + low(quote, z).count_ones() as usize;
                            let r = record(b, rs, p, qp - qr);
                            prefetch(entry(r.rid));
                            batch[nb & (BATCH - 1)] = r;
                            (rs, qr, nb) = (p + 1, qp, nb + 1);
                            if nb == BATCH {
                                flush(&batch, &mut agg, &mut out);
                                nb = 0;
                            }
                        }
                        qs += quote.count_ones() as usize;
                        base += 64;
                    }
                    mark(&mut agg); // after every 64 KiB, so few blocks wait in the inbox
                    if done {
                        break;
                    }
                    let shift = rs - 32;
                    if shift == 0 {
                        buf.resize(2 * buf.len() - 64, 0); // one record fills the buffer
                        continue;
                    }
                    buf.copy_within(shift..filled, 0);
                    (off, filled) = (off + shift, filled - shift);
                    (base, rs) = (base - shift, rs - shift);
                }
            }
            flush(&batch[..nb], &mut agg, &mut out);
            for (o, v) in out.into_iter().enumerate() {
                inbox[o].0.lock().unwrap().push(v);
            }
            barrier.wait();
            mark(&mut agg);
            let mut sum = total.lock().unwrap();
            (0..256).for_each(|g| merge(&mut sum[g], agg[g]));
            drop(sum);
            barrier.wait();
            full.load(Relaxed)
        };
        // Worker 0, the main thread, writes the output and ends the process; the others wait
        // for that, so no thread is torn down.
        let work = &work;
        thread::scope(|s| {
            for t in 1..n {
                s.spawn(move || {
                    if !work(t) {
                        loop {
                            thread::park();
                        }
                    }
                });
            }
            if !work(0) {
                report(&total.lock().unwrap(), &group, &out);
                std::process::exit(0);
            }
        });
        slots *= 2;
    }
}
