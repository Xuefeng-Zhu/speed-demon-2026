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

/// Asks the CPU to start loading the cache line at `p`, ready to be written, without waiting.
fn prefetch<T>(p: &T) {
    #[cfg(target_arch = "x86_64")]
    unsafe {
        asm!("prefetchw [{}]", in(reg) p, options(nomem, nostack))
    };
    #[cfg(target_arch = "aarch64")]
    unsafe {
        asm!("prfm pstl1keep, [{}]", in(reg) p, options(nomem, nostack))
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

/// The shared name dictionary: an open-addressing table with one 64-byte cache line per
/// name, holding [state, key words 0..3, group bitset 0..4]. State 0 is empty, 1 is being
/// written, 2 + len is a name of `len` <= 24 bytes kept inline in the key words, and 27 a
/// longer name, whose key is its number in `long`.
struct Names {
    slots: &'static [[AtomicU64; 8]],
    long: Mutex<HashMap<Box<[u8]>, u64>>,
    used: Own<AtomicUsize>, // written on every insert, so kept off the line read per record
}
#[repr(align(128))]
struct Own<T>(T);
impl Names {
    fn full(&self) -> bool {
        self.used.0.load(Relaxed) > self.slots.len() / 8 * 7
    }
    /// The key of the name `b[s..e]` and its first slot, whose cache line starts loading now.
    fn key(&self, b: &[u8], s: usize, e: usize) -> ([u64; 4], usize) {
        let (len, w) = ((e - s) as u64, [0, 8, 16].map(|o| word(b, s + o, e)));
        let key = match len {
            0..=24 => [w[0], w[1], w[2], 2 + len],
            _ => {
                let mut long = self.long.lock().unwrap();
                let id = long.len() as u64;
                [*long.entry(b[s..e].into()).or_insert(id), 0, 0, 27]
            }
        };
        let h = key
            .into_iter()
            .fold(0, |h: u64, w| (h.rotate_left(5) ^ w).wrapping_mul(K));
        let i = (h >> (64 - self.slots.len().trailing_zeros())) as usize;
        prefetch(&self.slots[i]);
        prefetch(&self.slots[(i + 1) & (self.slots.len() - 1)]); // a probe may go on
        (key, i)
    }
    /// Notes that the name with this key occurs in group `g`; returns 1 the first time, else
    /// 0. Once the table is too full it stops inserting, and the run starts over.
    fn see(&self, (key, mut i): ([u64; 4], usize), g: usize) -> i64 {
        let slot = loop {
            let slot = &self.slots[i];
            let mut state = slot[0].load(Acquire);
            if state == 0 && self.full() {
                return 0;
            } else if state == 0 && slot[0].compare_exchange(0, 1, Acquire, Acquire).is_ok() {
                (0..3).for_each(|j| slot[j + 1].store(key[j], Relaxed));
                slot[0].store(key[3], Release);
                self.used.0.fetch_add(1, Relaxed);
                break slot;
            }
            while state <= 1 {
                state = slot[0].load(Acquire); // wait while another thread writes the slot
            }
            if state == key[3] && (0..3).all(|j| slot[j + 1].load(Relaxed) == key[j]) {
                break slot;
            }
            i = (i + 1) & (self.slots.len() - 1);
        };
        let (bit, w) = (1 << (g % 64), &slot[4 + g / 64]);
        (w.load(Relaxed) & bit == 0 && w.fetch_or(bit, Relaxed) & bit == 0) as i64
    }
}
const K: u64 = 0x517cc1b727220a95; // FxHash's multiplier
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
    let recs = map(format!("{data}/records.csv"));
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
        let names = Names {
            slots: zeroed(1 << bits),
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
            let mut ring = [(([0; 4], 0), 0, EMPTY); RING];
            let mut finish = |(key, rid, mut rec): (_, usize, Agg)| {
                let g = region.get(rid).map_or(0, |r| r.load(Relaxed)) as usize;
                if rec[0] > 0 {
                    rec[5] = names.see(key, g); // not for the empty entries the ring starts with
                    merge(&mut agg[g], rec);
                }
            };
            let mut r = 0;
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
                        region.get(rid).map(prefetch);
                        let neg = recs[f[3] + 1] == b'-';
                        let mut i = f[3] + 1 + neg as usize;
                        let int = digits(recs, &mut i) as i64;
                        let w = ld(recs, i); // ".dd"
                        let cents = int * 100 + (w >> 8 & 15) as i64 * 10 + (w >> 16 & 15) as i64;
                        let cents = [cents, -cents][neg as usize];
                        let rec = [1, id, cents, cents, cents, 0, len(0) as i64, len(1) as i64];
                        finish(ring[r]);
                        (ring[r], r) = ((names.key(recs, s, e), rid, rec), (r + 1) % RING);
                        (rs, k) = (p + 1, 0);
                    }
                    qs += quote.count_ones() as usize;
                    base += 64;
                }
            }
            ring.into_iter().for_each(finish);
            agg
        });
        if !names.full() {
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
