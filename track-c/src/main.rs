//! Speed Demon 2026, Track C (Join): std-only Rust. README.md explains the design.
use std::arch::asm;
use std::sync::atomic::{AtomicU64, AtomicU8, AtomicUsize, Ordering::*};
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
        asm!("prefetcht0 [{}]", in(reg) p, options(nomem, nostack))
    };
    #[cfg(target_arch = "aarch64")]
    unsafe {
        asm!("prfm pldl1keep, [{}]", in(reg) p, options(nomem, nostack))
    };
}

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

/// The number whose decimal digits fill the top `n` (1 to 8) bytes of `x`, eight at once.
fn num(x: u64, n: usize) -> u64 {
    let mut v = x & 0x0F0F0F0F0F0F0F0F & !0 << (64 - 8 * n);
    v = (v * 10 + (v >> 8)) & 0x00FF00FF00FF00FF;
    v = (v * 100 + (v >> 16)) & 0x0000FFFF0000FFFF;
    (v * 10000 + (v >> 32)) & 0xFFFFFFFF
}

/// The shared name dictionary, read-mostly: an open-addressing table of 32-byte entries
/// [key words 0..2, state]. The key is the name's bytes padded with zeros (names hold no
/// NUL), or for names over 24 bytes their number in `long` and !0. State 0 is empty, 1 is
/// being written, 2 + id a name with a dense id, so the bitmaps of the groups stay small.
struct Names {
    slots: &'static [[AtomicU64; 4]],
    long: Mutex<HashMap<Box<[u8]>, u64>>,
    used: AtomicUsize,
}
impl Names {
    /// The key of the name `b[s..e]` and its first slot, whose cache line starts loading now.
    fn key(&self, b: &[u8], s: usize, e: usize) -> ([u64; 3], usize) {
        let key = match e - s {
            0..=24 => [0, 8, 16].map(|o| word(b, s + o, e)),
            _ => {
                let mut long = self.long.lock().unwrap();
                let id = long.len() as u64;
                [*long.entry(b[s..e].into()).or_insert(id), 0, !0]
            }
        };
        let h = key
            .iter()
            .fold(0, |h: u64, &w| (h.rotate_left(5) ^ w).wrapping_mul(K));
        let i = (h >> (64 - self.slots.len().trailing_zeros())) as usize;
        prefetch(&self.slots[i]);
        prefetch(&self.slots[(i + 2) & (self.slots.len() - 1)]); // a probe may go on
        (key, i)
    }
    /// The id of the name with this key, inserting it if new. Ids from `cap` up mean the
    /// table is too full: the run then starts over with a larger one.
    fn id(&self, (key, mut i): ([u64; 3], usize), cap: usize) -> usize {
        loop {
            let slot = &self.slots[i];
            let mut state = slot[3].load(Acquire);
            if state == 0 && slot[3].compare_exchange(0, 1, Acquire, Acquire).is_ok() {
                let id = self.used.fetch_add(1, Relaxed);
                (0..3).for_each(|j| slot[j].store(key[j], Relaxed));
                slot[3].store(2 + id as u64, Release);
                return id;
            }
            while state <= 1 {
                state = slot[3].load(Acquire); // wait while another thread writes the slot
            }
            if (0..3).all(|j| slot[j].load(Relaxed) == key[j]) {
                return state as usize - 2;
            }
            i = (i + 1) & (self.slots.len() - 1);
            if self.used.load(Relaxed) >= cap {
                return cap;
            }
        }
    }
}
const K: u64 = 0x517cc1b727220a95; // FxHash's multiplier
const RING: usize = 16;
const BLOCK: usize = 1024;

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
    let recs = map(format!("{data}/records.csv"));
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
    // Records are cut into 64 chunks per thread, each moved to start after a CRLF: CR only
    // ever occurs in a record terminator (spec 2.2), so this needs no knowledge of quotes.
    let start = recs.iter().position(|&c| c == b'\n').unwrap() + 1;
    let chunks = 64 * n;
    let bound = |c: usize| match c {
        0 => start,
        _ if c == chunks => recs.len(),
        _ => {
            let cut = start + (recs.len() - start) * c / chunks;
            recs[cut..]
                .iter()
                .position(|&c| c == b'\r')
                .map_or(recs.len(), |i| cut + i + 2)
        }
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
            long: Default::default(),
            used: 0.into(),
        };
        // seen_in[g * stride + id / 64] bit id % 64: name id occurs in group g. Group g is
        // owned by thread g % n, which alone reads and writes its bits; the others hand it
        // the (id, g) pairs they find in blocks of BLOCK, through its inbox.
        let stride = cap / 64 + 1;
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
                for v in std::mem::take(&mut *inbox[t].lock().unwrap()) {
                    for x in v {
                        let (g, id) = ((x & 255) as usize, (x >> 8) as usize);
                        let (word, bit) = (&seen_in[g * stride + id / 64], 1 << (id % 64));
                        let old = word.load(Relaxed);
                        word.store(old | bit, Relaxed);
                        agg[g][5] += (old & bit == 0) as i64;
                    }
                }
            };
            let mut ring = [(([0; 3], 0), 0, EMPTY); RING];
            let finish =
                |(key, rid, rec): (_, usize, Agg), agg: &mut Vec<Agg>, out: &mut Vec<Vec<u32>>| {
                    if rec[0] > 0 {
                        let (id, g) = (
                            names.id(key, cap),
                            region.get(rid).map_or(0, |r| r.load(Relaxed)) as usize,
                        );
                        merge(&mut agg[g], rec);
                        let o = &mut out[g % n];
                        o.push((id.min(cap) as u32) << 8 | g as u32);
                        if o.len() == BLOCK {
                            let full = std::mem::replace(o, Vec::with_capacity(BLOCK));
                            inbox[g % n].lock().unwrap().push(full);
                        }
                    }
                };
            let mut r = 0;
            {
                let claim = || Some(next.fetch_add(1, Relaxed)).filter(|&c| c < chunks);
                while let Some(c) = claim() {
                    // Masks of quotes, commas and LFs, 64 bytes at a time. A byte is inside quotes
                    // when an odd number of quotes precede it in the record, so the commas and LFs
                    // outside quotes are the field and record ends. f holds the field ends, q the
                    // number of quotes before each.
                    let (mut base, end) = (bound(c), bound(c + 1));
                    let (mut rs, mut k, mut f, mut q, mut qs, mut carry) =
                        (base, 0, [0; 4], [0; 4], 0, 0);
                    let last = (end == recs.len()) as usize; // whose last record may lack its LF
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
                            let (t, p) =
                                (ends.trailing_zeros(), base + ends.trailing_zeros() as usize);
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
                            // Each number is read from the eight bytes that end where it ends (ids
                            // have at most 8 digits, regions 7 and amounts 7 with the cents).
                            let i = rs + 3 * (recs[rs] == 0xEF) as usize;
                            let id = num(ld(recs, f[0] - 8), f[0] - i) as i64;
                            let len = |j: usize| {
                                f[j + 1]
                                    - f[j]
                                    - 1
                                    - (q[j + 1] - q[j]) / 2
                                    - (q[j + 1] > q[j]) as usize
                            };
                            let quoted = (q[1] > q[0]) as usize;
                            let (s, e) = (f[0] + 1 + quoted, f[1] - quoted);
                            let rid = num(ld(recs, f[3] - 8), f[3] - f[2] - 1) as usize;
                            region.get(rid).map(prefetch);
                            let neg = recs[f[3] + 1] == b'-';
                            let ae = p - (recs[p - 1] == b'\r') as usize;
                            let x = ld(recs, ae - 8); // ...ddd.dd: drop the '.'
                            let x = (x & 0xFF_FFFF_FFFF) << 8 | x & 0xFFFF << 48;
                            let cents = num(x, ae - f[3] - 2 - neg as usize) as i64;
                            let cents = [cents, -cents][neg as usize];
                            let rec = [1, id, cents, cents, cents, 0, len(0) as i64, len(1) as i64];
                            finish(ring[r], &mut agg, &mut out);
                            (ring[r], r) = ((names.key(recs, s, e), rid, rec), (r + 1) % RING);
                            (rs, k) = (p + 1, 0);
                        }
                        qs += quote.count_ones() as usize;
                        base += 64;
                    }
                    // MADV_DONTNEED the chunk's pages now, in parallel, not at exit on one thread
                    // (a read past the chunk's end faults the page back in).
                    let page = bound(c) & !4095;
                    unsafe { madvise(recs.as_ptr().add(page) as _, end - page, 4) };
                    mark(&mut agg);
                }
                for j in 0..RING {
                    finish(ring[(r + j) % RING], &mut agg, &mut out);
                    ring[(r + j) % RING].2[0] = 0;
                }
                for (o, v) in out.into_iter().enumerate() {
                    inbox[o].lock().unwrap().push(v);
                }
                barrier.wait();
                mark(&mut agg);
            }
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
