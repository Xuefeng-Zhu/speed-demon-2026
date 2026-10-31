//! Speed Demon 2026, Track C (Join): std-only Rust. README.md explains the design.
use std::arch::asm;
use std::sync::atomic::{AtomicU32, AtomicU64, AtomicU8, AtomicUsize, Ordering::*};
use std::{collections::HashMap, env, fs, os::fd::AsRawFd, sync::Barrier, sync::Mutex, thread};

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
fn zeroed<T>(n: usize) -> &'static [T] {
    let len = n * std::mem::size_of::<T>();
    let p = unsafe { mmap(0 as _, len, 3, 0x22, -1, 0) };
    unsafe { madvise(p, len, 14) }; // MADV_HUGEPAGE: fewer TLB misses
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

/// Asks the CPU to start loading the cache line at `p` without waiting: ready to be written
/// (taking it from other cores) if `W`, else shared, for lines that every thread only reads.
fn prefetch<const W: bool, T>(p: &T) {
    #[cfg(target_arch = "x86_64")]
    unsafe {
        match W {
            true => asm!("prefetchw [{}]", in(reg) p, options(nomem, nostack)),
            _ => asm!("prefetcht0 [{}]", in(reg) p, options(nomem, nostack)),
        }
    };
    #[cfg(target_arch = "aarch64")]
    unsafe {
        match W {
            true => asm!("prfm pstl1keep, [{}]", in(reg) p, options(nomem, nostack)),
            _ => asm!("prfm pldl1keep, [{}]", in(reg) p, options(nomem, nostack)),
        }
    };
}

const H: u64 = 0x8080808080808080;

/// Bytes `p..p + 8` of `b` as a little-endian word, padded with zeros past the end.
fn ld(b: &[u8], p: usize) -> u64 {
    match b.get(p..p + 8) {
        Some(w) => u64::from_le_bytes(w.try_into().unwrap()),
        None => b[p..].iter().rev().fold(0, |w, &c| w << 8 | c as u64),
    }
}

/// Bytes `s..e` of `b`, at most eight of them, as a little-endian word padded with zeros.
fn word(b: &[u8], s: usize, e: usize) -> u64 {
    let n = e.saturating_sub(s).min(8);
    ld(b, s.min(e)) & ((1u128 << (8 * n)) - 1) as u64
}

/// Parses the decimal digits at `p` and moves `p` to the byte after them: up to eight at
/// once (every byte below '0' ends them: ',', '.', CR, LF), more one by one.
fn digits(b: &[u8], p: &mut usize) -> u64 {
    let x = ld(b, *p);
    let t = (x & 0xF0F0F0F0F0F0F0F0) ^ 0x3030303030303030; // zero bytes are digits
    let n = ((t | (t & !H).wrapping_add(!H)) & H).trailing_zeros() as usize / 8;
    let mut v = (x & 0x0F0F0F0F0F0F0F0F).wrapping_shl(64 - 8 * n as u32) * (n > 0) as u64;
    v = (v * 10 + (v >> 8)) & 0x00FF00FF00FF00FF;
    v = (v * 100 + (v >> 16)) & 0x0000FFFF0000FFFF;
    v = (v * 10000 + (v >> 32)) & 0xFFFFFFFF;
    *p += n;
    while let Some(c @ b'0'..=b'9') = b.get(*p) {
        (v, *p) = (v * 10 + (c - b'0') as u64, *p + 1);
    }
    v
}

/// The shared name dictionary. `index` is a small open-addressing table (under half full)
/// of u32s: a hash tag in the high bits and 1 + the name's number in the low `bits`. Each
/// number owns one 64-byte line in `names`: [key words 0..4, group bitset 0..4]. The key is a
/// name of up to 32 bytes, zero-padded (names hold no zero bytes), or a longer one's number
/// in `long` followed by !0.
struct Names {
    index: &'static [AtomicU32],
    names: &'static [[AtomicU64; 8]],
    bits: u32,
    long: Mutex<HashMap<Box<[u8]>, u64>>,
    used: Own<AtomicUsize>, // written on every insert, so kept off the lines read per record
}
#[repr(align(128))]
struct Own<T>(T);
impl Names {
    /// The key of the name `b[s..e]` and its slot and number; its line starts loading now.
    fn key(&self, b: &[u8], s: usize, e: usize) -> ([u64; 4], usize, usize) {
        let mut key = [0, 8, 16, 24].map(|o| word(b, s + o, e));
        if e - s > 32 {
            let mut long = self.long.lock().unwrap();
            let id = long.len() as u64;
            key = [*long.entry(b[s..e].into()).or_insert(id), !0, 0, 0];
        }
        let i = (hash(key) >> (63 - self.bits)) as usize;
        prefetch::<false, _>(&self.index[i]);
        (key, i, 0)
    }
    /// Looks up a key's number, once its slot has loaded, and starts loading its line.
    fn locate(&self, (key, i, id): &mut ([u64; 4], usize, usize)) {
        (*i, *id) = self.find(*key, *i);
        self.names.get(*id).map(prefetch::<true, _>);
    }
    /// The first slot from `i` on whose tag matches `key` (inserting it if a free slot comes
    /// first) and the number there; usize::MAX once the table is full.
    fn find(&self, key: [u64; 4], mut i: usize) -> (usize, usize) {
        let tag = hash(key) as u32 >> self.bits << self.bits;
        loop {
            let slot = &self.index[i];
            let mut v = slot.load(Acquire);
            if v == 0 {
                let id = self.used.0.fetch_add(1, Relaxed);
                let Some(line) = self.names.get(id) else {
                    return (i, usize::MAX);
                };
                (0..4).for_each(|j| line[j].store(key[j], Relaxed));
                match slot.compare_exchange(0, tag | (id + 1) as u32, Release, Acquire) {
                    Ok(_) => return (i, id),
                    Err(now) => v = now,
                }
            }
            if v >> self.bits << self.bits == tag {
                return (i, (v & ((1 << self.bits) - 1)) as usize - 1);
            }
            i = (i + 1) & (self.index.len() - 1);
        }
    }
    /// Notes that the name occurs in group `g`; returns 1 the first time, else 0.
    fn see(&self, (key, mut i, mut id): ([u64; 4], usize, usize), g: usize) -> i64 {
        loop {
            let Some(line) = self.names.get(id) else {
                return 0; // full: the run starts over
            };
            if (0..4).all(|j| line[j].load(Relaxed) == key[j]) {
                let (bit, w) = (1 << (g % 64), &line[4 + g / 64]);
                return (w.load(Relaxed) & bit == 0 && w.fetch_or(bit, Relaxed) & bit == 0) as i64;
            }
            (i, id) = self.find(key, (i + 1) & (self.index.len() - 1)); // a tag collision
        }
    }
}
fn hash(key: [u64; 4]) -> u64 {
    key.into_iter().fold(0, |h: u64, w| {
        (h.rotate_left(5) ^ w).wrapping_mul(0x517cc1b727220a95)
    }) // FxHash
}
const RING: usize = 16;

/// Bit i of each mask is set where byte i of the block is a quote, a comma or an LF.
#[cfg(target_feature = "avx2")]
fn masks(p: &[u8; 64]) -> [u64; 3] {
    use std::arch::x86_64::*;
    unsafe {
        let v = [0, 32].map(|o| _mm256_loadu_si256(p.as_ptr().add(o) as _));
        let m = |v, c| _mm256_movemask_epi8(_mm256_cmpeq_epi8(v, _mm256_set1_epi8(c))) as u32;
        [b'"', b',', b'\n'].map(|c| m(v[0], c as i8) as u64 | (m(v[1], c as i8) as u64) << 32)
    }
}
#[cfg(not(target_feature = "avx2"))] // portable, slow; the scoring box has AVX2
fn masks(p: &[u8; 64]) -> [u64; 3] {
    [b'"', b',', b'\n'].map(|c| (0..64).fold(0, |m, i| m | ((p[i] == c) as u64) << i))
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
    let file = fs::File::open(format!("{data}/records.csv")).unwrap();
    let len = file.metadata().unwrap().len() as usize;
    let regs = map(format!("{data}/regions.csv"));
    let n = thread::available_parallelism().map_or(1, |n| n.get());
    // regions.csv is sorted, so its last line holds the largest region id.
    let last = regs[..regs.len() - 1]
        .iter()
        .rposition(|&c| c == b'\n')
        .unwrap()
        + 1;
    let region: &[AtomicU8] = zeroed(digits(regs, &mut { last }) as usize + 1);
    let seen: Vec<AtomicU8> = (0..17577).map(|_| AtomicU8::new(0)).collect();
    // Records are read in 32 KB chunks, each moved to start after a CRLF: CR only ever
    // occurs in a record terminator (spec 2.2), the header's included, so this needs no
    // knowledge of quotes.
    let chunks = (len >> 15).max(1);
    let crlf = |b: &[u8], i| Some(i + 2 + b.get(i..b.len() - 1)?.iter().position(|&c| c == 13)?);
    let rstart = regs.iter().position(|&c| c == b'\n').unwrap() + 1;
    let rcut = |t: usize| match t {
        0 => rstart,
        _ => (rstart + (regs.len() - rstart) * t / n..regs.len())
            .find(|&i| regs[i - 1] == b'\n')
            .unwrap_or(regs.len()),
    };
    let mut bits = 17; // room for 2^17 names; four times as many whenever they run out
    let aggs = loop {
        let names = Names {
            index: zeroed(2 << bits),
            names: zeroed(7 << bits >> 3),
            bits,
            long: Default::default(),
            used: Own(0.into()),
        };
        let (next, barrier) = (AtomicUsize::new(0), Barrier::new(n));
        let aggs = par(n, |t| {
            // Every thread reads its share of the regions twice: first to note which countries
            // occur, then to map each region id to its country's group. Groups are numbered in
            // key order, so the output needs no sort; group 0 (no country) is _UNMATCHED.
            let mut group = [0u8; 17577];
            for pass in 0..2 {
                let (mut p, end) = (rcut(t), if t + 1 == n { regs.len() } else { rcut(t + 1) });
                while p < end {
                    let id = digits(regs, &mut p) as usize;
                    let c = code(&regs[p + 1..p + 4]);
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
            let mut ring = [(([0; 4], 0, 0), 0, EMPTY); RING];
            let mut finish = |(key, rid, mut rec): (_, usize, Agg)| {
                let g = region.get(rid).map_or(0, |r| r.load(Relaxed)) as usize;
                if rec[0] > 0 {
                    rec[5] = names.see(key, g); // not for the empty entries the ring starts with
                    merge(&mut agg[g], rec);
                }
            };
            let (mut r, mut buf) = (0, vec![]);
            let claim = || Some(next.fetch_add(1, Relaxed)).filter(|&c| c < chunks);
            while let Some(c) = claim() {
                // The chunk, and as much more as it takes to reach the CRLF its last record ends
                // with, is read into buf (its pages stay in the shared page cache, unmapped).
                let (lo, hi, mut pad) = (len * c / chunks, len * (c + 1) / chunks, 1 << 12);
                let end = loop {
                    buf.resize((hi + pad).min(len) - lo, 0);
                    std::os::unix::fs::FileExt::read_exact_at(&file, &mut buf, lo as u64).unwrap();
                    match crlf(&buf, hi - lo) {
                        Some(e) => break e,
                        None if lo + buf.len() == len => break buf.len(),
                        None => pad *= 2,
                    }
                };
                // Masks of quotes, commas and LFs, 64 bytes at a time. A byte is inside quotes
                // when an odd number of quotes precede it in the record, so the commas and LFs
                // outside quotes are the field and record ends. f holds the field ends, q the
                // number of quotes before each.
                let (recs, mut base) = (&buf[..], crlf(&buf, 0).unwrap_or(end).min(end));
                let (mut rs, mut k, mut f, mut q, mut qs, mut carry) =
                    (base, 0, [0; 4], [0; 4], 0, 0);
                let last = (lo + end == len) as usize; // whose last record may lack its LF
                while base < end + last {
                    let mut pad = [0; 64]; // the end of the file, padded, then an LF
                    let block = recs.get(base..base + 64).unwrap_or_else(|| {
                        pad[..recs.len() - base].copy_from_slice(&recs[base..]);
                        pad[recs.len() - base] = b'\n';
                        &pad
                    });
                    let [quote, comma, lf] = masks(block.try_into().unwrap());
                    let mut inside =
                        [1, 2, 4, 8, 16, 32].iter().fold(quote, |x, s| x ^ x << s) ^ carry;
                    carry = 0u64.wrapping_sub(inside >> 63);
                    inside |= u64::MAX
                        .checked_shl((end + last - base) as u32)
                        .unwrap_or(0);
                    let mut ends = (comma | lf) & !inside;
                    while ends != 0 {
                        let (t, p) = (ends.trailing_zeros(), base + ends.trailing_zeros() as usize);
                        ends &= ends - 1;
                        if k < 4 {
                            (f[k], q[k], k) = (
                                p,
                                qs + (quote & ((1 << t) - 1)).count_ones() as usize,
                                k + 1,
                            );
                            continue;
                        }
                        // A record: [BOM] id , name , note , region , amount [CR] LF
                        let mut i = rs + 3 * (recs[rs] == 0xEF) as usize;
                        let id = digits(recs, &mut i) as i64;
                        let len = |j: usize| {
                            f[j + 1] - f[j] - 1 - (q[j + 1] - q[j]) / 2 - (q[j + 1] > q[j]) as usize
                        };
                        let quoted = (q[1] > q[0]) as usize;
                        let (s, e) = (f[0] + 1 + quoted, f[1] - quoted);
                        let rid = digits(recs, &mut { f[2] + 1 }) as usize;
                        region.get(rid).map(prefetch::<false, _>);
                        let neg = recs[f[3] + 1] == b'-';
                        let mut i = f[3] + 1 + neg as usize;
                        let int = digits(recs, &mut i) as i64;
                        let w = ld(recs, i); // ".dd"
                        let cents = int * 100 + (w >> 8 & 15) as i64 * 10 + (w >> 16 & 15) as i64;
                        let cents = [cents, -cents][neg as usize];
                        let rec = [1, id, cents, cents, cents, 0, len(0) as i64, len(1) as i64];
                        finish(ring[r]);
                        let m = &mut ring[(r + RING / 2) % RING];
                        if m.2[0] > 0 {
                            names.locate(&mut m.0);
                        }
                        (ring[r], r) = ((names.key(recs, s, e), rid, rec), (r + 1) % RING);
                        (rs, k) = (p + 1, 0);
                    }
                    qs += quote.count_ones() as usize;
                    base += 64;
                }
            }
            for j in 0..RING {
                let m = &mut ring[(r + j + RING / 2) % RING];
                if m.2[0] > 0 && j < RING / 2 {
                    names.locate(&mut m.0);
                }
                finish(ring[(r + j) % RING]);
            }
            agg
        });
        if names.used.0.load(Relaxed) <= names.names.len() {
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
