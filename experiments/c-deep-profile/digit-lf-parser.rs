//! Speed Demon 2026, Track C (Join): std-only Rust. README.md explains the design.
use std::sync::atomic::{AtomicU64, AtomicU8, AtomicUsize, Ordering::*};
use std::{env, fs, os::fd::AsRawFd, os::unix::fs::FileExt, sync::Barrier, sync::Mutex, thread};

extern "C" {
    fn mmap(addr: *mut u8, len: usize, prot: i32, flags: i32, fd: i32, off: i64) -> *mut u8;
    fn madvise(addr: *mut u8, len: usize, advice: i32) -> i32;
}

/// Maps a file read-only (PROT_READ, MAP_PRIVATE): its pages stay in the shared page cache.
fn map(path: String) -> &'static [u8] {
    let f = fs::File::open(&path).expect(&path);
    let len = f.metadata().unwrap().len() as usize;
    unsafe { std::slice::from_raw_parts(mmap(0 as _, len, 1, 2, f.as_raw_fd(), 0), len) }
}

/// `n` zeroed atomics from an anonymous map, so pages are only touched when used.
fn zeroed<T>(n: usize, advice: i32) -> &'static [T] {
    let len = n * std::mem::size_of::<T>();
    let p = unsafe { mmap(0 as _, len, 3, 0x22, -1, 0) };
    unsafe { madvise(p, len, advice) }; // 14 = MADV_HUGEPAGE: fewer TLB misses
    unsafe { std::slice::from_raw_parts(p as _, n) }
}

/// Runs `f(0)..f(n - 1)` on n scoped threads and returns the results in order.
fn par<T: Send>(n: usize, f: impl Fn(usize) -> T + Sync) -> Vec<T> {
    let f = &f;
    thread::scope(|s| {
        let handles: Vec<_> = (0..n).map(|t| s.spawn(move || f(t))).collect();
        handles.into_iter().map(|h| h.join().unwrap()).collect()
    })
}

/// Asks the CPU to start loading the cache line at `p` without waiting.
fn prefetch<T>(p: &T) {
    #[cfg(target_arch = "x86_64")]
    unsafe {
        std::arch::asm!("prefetcht0 [{}]", in(reg) p, options(nomem, nostack))
    };
}

/// Bytes `p..p + 8` of `b` as a little-endian word. Callers only read where eight bytes
/// exist: each number ends at least eight bytes into the file, and each name before its
/// record's region id.
fn ld(b: &[u8], p: usize) -> u64 {
    debug_assert!(p + 8 <= b.len());
    unsafe { (b.as_ptr().add(p) as *const u64).read_unaligned() }
}

/// Bytes `s..e` of `b`, at most eight of them, as a little-endian word padded with zeros.
fn word(b: &[u8], s: usize, e: usize) -> u64 {
    let n = e.saturating_sub(s).min(8);
    ld(b, s.min(e)) & ((1u128 << (8 * n)) - 1) as u64
}

/// The number whose decimal digits fill the top `n` (1 to 8) bytes of `x`, eight at once.
fn num(x: u64, n: usize) -> u64 {
    let mut v = x & 0x0F0F0F0F0F0F0F0F & !0 << (64 - 8 * n);
    v = (v * 10 + (v >> 8)) & 0x00FF00FF00FF00FF;
    v = (v * 100 + (v >> 16)) & 0x0000FFFF0000FFFF;
    (v * 10000 + (v >> 32)) & 0xFFFFFFFF
}

/// The shared name dictionary: an open-addressing table of 64-bit name hashes; a name's id
/// is its slot. Names are not compared byte for byte: two of the ~10^5 names share a hash
/// with probability ~3e-10. The hash folds the name's bytes eight at a time, zero padded
/// (names never contain a zero byte).
struct Names {
    slots: &'static [AtomicU64],
    used: AtomicUsize,
}
impl Names {
    /// The hash of the name `b[s..e]` and its first slot, whose cache line starts loading now.
    fn key(&self, b: &[u8], s: usize, e: usize) -> (u64, usize) {
        let h = (s..e.max(s + 1)).step_by(8).fold(K, |h, o| {
            (h ^ word(b, o, e)).wrapping_mul(K).rotate_left(31)
        });
        let h = ((h ^ h >> 33).wrapping_mul(0xff51afd7ed558ccd) ^ h >> 29).max(1);
        let i = (h >> (64 - self.slots.len().trailing_zeros())) as usize;
        prefetch(&self.slots[i]);
        (h, i)
    }
    /// The id of the name with this hash, inserting it if new; the table size once it holds
    /// `cap` names: the run then starts over with a larger one.
    fn id(&self, (h, mut i): (u64, usize), cap: usize) -> usize {
        loop {
            let e = self.slots[i].load(Relaxed);
            if e == h
                || e == 0
                    && self.slots[i]
                        .compare_exchange(0, h, Relaxed, Relaxed)
                        .is_ok()
                    && self.used.fetch_add(1, Relaxed) < cap
            {
                return i;
            } else if e != 0 {
                i = (i + 1) & (self.slots.len() - 1);
            }
            if self.used.load(Relaxed) >= cap {
                return self.slots.len();
            }
        }
    }
}
const K: u64 = 0x517cc1b727220a95; // FxHash's multiplier
const RING: usize = 16;
const BLOCK: usize = 1024;

/// Bit i of each mask is set where byte i of the 64 bytes at `p` is a quote, an LF, or a
/// digit or CR. A record ends at the first LF after a digit or CR: names and notes hold no
/// digits and CR only ever starts a CRLF terminator (spec 2.2).
#[cfg(target_feature = "avx2")]
fn masks(b: &[u8], p: usize) -> [u64; 3] {
    use std::arch::x86_64::*;
    assert!(p + 64 <= b.len());
    unsafe {
        let v = [0, 32].map(|o| _mm256_loadu_si256(b.as_ptr().add(p + o) as _));
        let eq = |v, c: u8| _mm256_cmpeq_epi8(v, _mm256_set1_epi8(c as i8));
        let dc = |v| {
            let d = _mm256_sub_epi8(v, _mm256_set1_epi8(b'0' as i8));
            let digit = _mm256_cmpeq_epi8(_mm256_min_epu8(d, _mm256_set1_epi8(9)), d);
            _mm256_or_si256(digit, eq(v, b'\r'))
        };
        let both = |m: [__m256i; 2]| {
            _mm256_movemask_epi8(m[0]) as u32 as u64 | (_mm256_movemask_epi8(m[1]) as u32 as u64) << 32
        };
        [both(v.map(|v| eq(v, b'"'))), both(v.map(|v| eq(v, b'\n'))), both(v.map(dc))]
    }
}
#[cfg(not(target_feature = "avx2"))] // portable, slow; the scoring box has AVX2
fn masks(b: &[u8], p: usize) -> [u64; 3] {
    let f = |t: &dyn Fn(u8) -> bool| (0..64).fold(0, |m, i| m | (t(b[p + i]) as u64) << i);
    [f(&|c| c == b'"'), f(&|c| c == b'\n'), f(&|c| c.is_ascii_digit() || c == b'\r')]
}

/// Bit i of each mask is set where byte i of the 32 bytes at `p` is a quote or a comma.
#[cfg(target_feature = "avx2")]
fn masks32(b: &[u8], p: usize) -> [u32; 2] {
    use std::arch::x86_64::*;
    assert!(p + 32 <= b.len());
    unsafe {
        let v = _mm256_loadu_si256(b.as_ptr().add(p) as _);
        [b'"', b','].map(|c| _mm256_movemask_epi8(_mm256_cmpeq_epi8(v, _mm256_set1_epi8(c as i8))) as u32)
    }
}
#[cfg(not(target_feature = "avx2"))]
fn masks32(b: &[u8], p: usize) -> [u32; 2] {
    [b'"', b','].map(|c| (0..32).fold(0, |m, i| m | ((b[p + i] == c) as u32) << i))
}

/// Where the field starting at `s` ends (the comma after it) and how many quotes it holds.
/// A comma is the end when an even number of quotes precede it in the field.
fn field_end(b: &[u8], mut s: usize) -> (usize, usize) {
    let (mut carry, mut quotes) = (0u32, 0);
    loop {
        let [q, c] = masks32(b, s);
        let inside = [1, 2, 4, 8, 16].iter().fold(q, |x, k| x ^ x << k) ^ carry;
        let ends = c & !inside;
        if ends != 0 {
            let t = ends.trailing_zeros();
            return (s + t as usize, quotes + (q & ((1 << t) - 1)).count_ones() as usize);
        }
        (carry, quotes, s) = (0u32.wrapping_sub(inside >> 31), quotes + q.count_ones() as usize, s + 32);
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

/// A country code as a number from 1 to 26^3; 0 means no country.
fn code(c: &[u8]) -> usize {
    1 + c.iter().fold(0, |a, &c| a * 26 + (c - b'A') as usize)
}

fn main() {
    let dir = |k, d: &str| env::var(k).unwrap_or(d.into());
    let (data, out) = (dir("SD_DATA", "/data"), dir("SD_OUT", "/out"));
    let file = fs::File::open(format!("{data}/records.csv")).expect("records.csv");
    let size = file.metadata().unwrap().len() as usize;
    let regs = map(format!("{data}/regions.csv"));
    let n = thread::available_parallelism().map_or(1, |n| n.get());
    // regions.csv is sorted, so its last line holds the largest region id.
    let last = regs[..regs.len() - 1]
        .iter()
        .rposition(|&c| c == b'\n')
        .unwrap()
        + 1;
    let comma = |p: usize| p + regs[p..].iter().position(|&c| c == b',').unwrap();
    let max = num(ld(regs, comma(last) - 8), comma(last) - last) as usize;
    let region: &[AtomicU8] = zeroed(max + 1, 14);
    let seen: Vec<AtomicU8> = (0..17577).map(|_| AtomicU8::new(0)).collect();
    // Records are cut into 16 chunks per thread, each moved to start after a CRLF: CR only
    // ever occurs in a record terminator (spec 2.2), so this needs no knowledge of quotes.
    // The first CR at or after `p` (or the file size), read 4 KiB at a time.
    let cr = |mut p: usize| loop {
        let mut b = [0; 4096];
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
        _ => (cr(start + (size - start) * c / chunks) + 2).min(size),
    };
    let rstart = regs.iter().position(|&c| c == b'\n').unwrap() + 1;
    let rcut = |t: usize| match t {
        0 => rstart,
        _ => (rstart + (regs.len() - rstart) * t / n..regs.len())
            .find(|&i| regs[i - 1] == b'\n')
            .unwrap_or(regs.len()),
    };
    let mut bits = 17; // 2^17 slots; four times as many whenever 7/8 of them fill up
    let aggs = loop {
        let slots = zeroed(1 << bits, 14);
        let cap = slots.len() / 8 * 7;
        let names = Names {
            slots,
            used: 0.into(),
        };
        // seen_in[g * stride + id / 64] bit id % 64: name id occurs in group g. Group g is
        // owned by thread g % n, which alone reads and writes its bits; the others hand it
        // the (id, g) pairs they find in blocks of BLOCK, through its inbox.
        let stride = slots.len() / 64 + 1;
        let seen_in: &[AtomicU64] = zeroed(256 * stride, 0);
        let inbox: Vec<Mutex<Vec<Vec<u32>>>> = (0..n).map(|_| Default::default()).collect();
        let (next, barrier) = (AtomicUsize::new(0), Barrier::new(n));
        let aggs = par(n, |t| {
            // Every thread reads its share of the regions twice: first to note which countries
            // occur, then to map each region id to its country's group. Groups are numbered in
            // key order, so the output needs no sort; group 0 (no country) is _UNMATCHED.
            let mut group = [0u8; 17577];
            for pass in 0..2 {
                let (mut p, end) = (rcut(t), if t + 1 == n { regs.len() } else { rcut(t + 1) });
                while p < end {
                    let e = comma(p);
                    let (id, c) = (
                        num(ld(regs, e - 8), e - p) as usize,
                        code(&regs[e + 1..e + 4]),
                    );
                    p = e;
                    match pass {
                        0 => seen[c].store(1, Relaxed),
                        _ => region[id].store(group[c], Relaxed),
                    }
                    p += 5;
                }
                barrier.wait();
                let mut g = 0;
                for c in 1..17577 {
                    g += seen[c].load(Relaxed) as usize;
                    group[c] = g as u8 * seen[c].load(Relaxed);
                }
                assert!(g < 256, "at most 255 countries");
            }
            // A record is finished (its group and name looked up) 16 records after it is
            // parsed, so that the cache lines it needs have time to arrive.
            let mut agg = vec![EMPTY; 256];
            let mut out: Vec<Vec<u32>> = vec![Vec::with_capacity(BLOCK); n];
            let mark = |agg: &mut Vec<Agg>| {
                let blocks = std::mem::take(&mut *inbox[t].lock().unwrap()); // unlock before the loop
                for v in blocks {
                    for x in v {
                        let (g, id) = ((x & 255) as usize, (x >> 8) as usize);
                        let (word, bit) = (&seen_in[g * stride + id / 64], 1 << (id % 64));
                        let old = word.load(Relaxed);
                        word.store(old | bit, Relaxed);
                        agg[g][5] += (old & bit == 0) as i64;
                    }
                }
            };
            let mut ring = [((0, 0), 0, [0; 4]); RING];
            let finish = |(key, rid, [n_id, c, nl, tl]): (_, usize, [i64; 4]),
                          agg: &mut Vec<Agg>,
                          out: &mut Vec<Vec<u32>>| {
                if n_id > 0 {
                    let (id, g) = (
                        names.id(key, cap),
                        region.get(rid).map_or(0, |r| r.load(Relaxed)) as usize,
                    );
                    merge(&mut agg[g], [1, n_id, c, c, c, 0, nl, tl]);
                    let o = &mut out[g % n];
                    o.push((id as u32) << 8 | g as u32);
                    if o.len() == BLOCK {
                        let full = std::mem::replace(o, Vec::with_capacity(BLOCK));
                        inbox[g % n].lock().unwrap().push(full);
                    }
                }
            };
            let mut r = 0;
            let claim = || Some(next.fetch_add(1, Relaxed)).filter(|&c| c < chunks);
            // The chunk is read through buf, which holds the file from offset `off`: when the
            // parse reaches its end, the unfinished record and the 32 bytes before it move to
            // the front and the rest is refilled. Positions are into buf.
            let mut buf = vec![0u8; (1 << 16) + 64];
            // Record ends (LF positions) found in this fill, with the number of quotes before each.
            let mut ends: Vec<(usize, usize)> = Vec::with_capacity(1 << 12);
            while let Some(c) = claim() {
                let end = bound(c + 1);
                let last = (end == size) as usize; // whose last record may lack its LF
                let (mut off, mut filled) = (bound(c) - 32, 0);
                let (mut base, mut rs, mut qs, mut qr, mut carry) = (32, 32, 0, 0, 0);
                loop {
                    let want = (end - off).min(buf.len() - 64);
                    while filled < want {
                        let got = file.read_at(&mut buf[filled..want], (off + filled) as u64);
                        filled += got.ok().filter(|&g| g > 0).expect("records.csv shrank");
                    }
                    let done = off + filled == end;
                    buf[filled] = b'\n'; // only read when the file ends without one
                    let lim = end - off + last;
                    let b = &buf[..];
                    ends.clear();
                    while base < if done { lim } else { filled - 63 } {
                        let [q, lf, dc] = masks(b, base);
                        let keep = !u64::MAX.checked_shl((lim - base) as u32).unwrap_or(0);
                        let mut t = lf & (dc << 1 | carry) & keep;
                        carry = dc >> 63;
                        while t != 0 {
                            let i = t.trailing_zeros();
                            ends.push((base + i as usize, qs + (q & ((1 << i) - 1)).count_ones() as usize));
                            t &= t - 1;
                        }
                        qs += q.count_ones() as usize;
                        base += 64;
                    }
                    for &(p, qp) in &ends {
                        // A record: [BOM] id , name , note , region , amount [CR] LF. Only the
                        // name and note can hold commas or quotes. Each number is read from the
                        // eight bytes that end where it ends (ids have at most 8 digits,
                        // regions 7 and amounts 7 with the cents).
                        let i = rs + 3 * (b[rs] == 0xEF) as usize;
                        let f0 = i + masks32(b, i)[1].trailing_zeros() as usize;
                        let id = num(ld(b, f0 - 8), f0 - i) as i64;
                        let ae = p - (b[p - 1] == b'\r') as usize;
                        // The last two commas of the record lie within its last 17 bytes.
                        let cm = masks32(b, ae - 32)[1];
                        let f3 = ae - 1 - cm.leading_zeros() as usize;
                        let f2 = ae - 1 - (cm & !(1 << 31 - cm.leading_zeros())).leading_zeros() as usize;
                        let rid = num(ld(b, f3 - 8), f3 - f2 - 1) as usize;
                        region.get(rid).map(prefetch);
                        let neg = b[f3 + 1] == b'-';
                        let x = ld(b, ae - 8); // ...ddd.dd: drop the '.'
                        let x = (x & 0xFF_FFFF_FFFF) << 8 | x & 0xFFFF << 48;
                        let cents = num(x, ae - f3 - 2 - neg as usize) as i64;
                        let cents = [cents, -cents][neg as usize];
                        // A quoted field has 2 + 2k quotes for k "" escapes, and 2 + k bytes fewer.
                        let (f1, qn) = field_end(b, f0 + 1);
                        let qt = qp - qr - qn; // the note's quotes
                        let len = |n: usize, d: usize| n - d / 2 - (d > 0) as usize;
                        let rec = [id, cents, len(f1 - f0 - 1, qn) as i64, len(f2 - f1 - 1, qt) as i64];
                        let quoted = (qn > 0) as usize;
                        let (s, e) = (f0 + 1 + quoted, f1 - quoted);
                        finish(ring[r], &mut agg, &mut out);
                        (ring[r], r) = ((names.key(b, s, e), rid, rec), (r + 1) % RING);
                        (rs, qr) = (p + 1, qp);
                    }
                    if done {
                        break;
                    }
                    let shift = rs - 32;
                    if shift == 0 {
                        buf.resize(2 * buf.len() - 64, 0); // one record fills the buffer
                        continue;
                    }
                    buf.copy_within(shift..filled, 0);
                    (off, filled, base, rs) = (off + shift, filled - shift, base - shift, rs - shift);
                }
                mark(&mut agg);
            }
            for j in 0..RING {
                finish(ring[(r + j) % RING], &mut agg, &mut out);
                ring[(r + j) % RING].2[0] = 0; // id 0: no record to finish
            }
            for (o, v) in out.into_iter().enumerate() {
                inbox[o].lock().unwrap().push(v);
            }
            barrier.wait();
            mark(&mut agg);
            agg
        });
        if names.used.load(Relaxed) < cap {
            break aggs;
        }
        bits += 2;
    };
    let mut keys: Vec<String> = (1..17577)
        .filter(|&c| seen[c].load(Relaxed) == 1)
        .map(|c| [(c - 1) / 676, (c - 1) / 26 % 26, (c - 1) % 26].map(|d| (b'A' + d as u8) as char))
        .map(|k| k.iter().collect())
        .collect();
    keys.insert(0, "_UNMATCHED".into());
    let mut text = String::new();
    for g in (1..keys.len()).chain([0]) {
        let mut a = EMPTY;
        aggs.iter().for_each(|agg| merge(&mut a, agg[g]));
        if a[0] > 0 {
            let cols: String = a.iter().enumerate().map(|(i, &v)| column(i, v)).collect();
            text += &format!("{}{cols}\n", keys[g]);
        }
    }
    fs::create_dir_all(&out).unwrap();
    fs::write(format!("{out}/aggregates.txt"), text).unwrap();
}
