//! Speed Demon 2026, Track C (Join): std-only Rust. README.md explains the design.
use std::arch::asm;
use std::sync::atomic::{AtomicU64, AtomicUsize, Ordering::*};
use std::{collections::HashMap, env, fs, os::fd::AsRawFd, sync::Mutex, thread};

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

/// Runs `f(0)..f(n - 1)` on n scoped threads and returns the results in order.
fn par<T: Send>(n: usize, f: impl Fn(usize) -> T + Sync) -> Vec<T> {
    let f = &f;
    thread::scope(|s| {
        let handles: Vec<_> = (0..n).map(|t| s.spawn(move || f(t))).collect();
        handles.into_iter().map(|h| h.join().unwrap()).collect()
    })
}

/// Asks the CPU to start loading the cache line at `p` without waiting for it.
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

/// Bytes `s..e` of `b`, at most eight of them, as a little-endian word padded with zeros.
fn word(b: &[u8], s: usize, e: usize) -> u64 {
    let n = e.saturating_sub(s).min(8);
    match b.get(s..s + 8) {
        Some(w) => u64::from_le_bytes(w.try_into().unwrap()) & ((1u128 << (8 * n)) - 1) as u64,
        None => (s..s + n).rev().fold(0, |w, i| w << 8 | b[i] as u64),
    }
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
    /// 2^bits zeroed slots from an anonymous map, so pages are only touched when used.
    fn new(bits: u32) -> Names {
        let p = unsafe { mmap(0 as _, 64 << bits, 3, 0x22, -1, 0) };
        unsafe { madvise(p, 64 << bits, 14) }; // MADV_HUGEPAGE: fewer TLB misses
        let slots = unsafe { std::slice::from_raw_parts(p as _, 1 << bits) };
        let (long, used) = (Default::default(), Own(0.into()));
        Names { slots, long, used }
    }
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
        let bit = 1 << (g % 64);
        (slot[4 + g / 64].fetch_or(bit, Relaxed) & bit == 0) as i64
    }
}
const K: u64 = 0x517cc1b727220a95; // FxHash's multiplier

/// Parses the text field at `p` and steps past the comma after it. Returns where the bytes
/// between the quotes start and end, still escaped (escaping is one-to-one, so equal raw
/// bytes mean equal values, and unquoted text never contains a quote), and the unescaped length.
fn field(b: &[u8], p: &mut usize) -> (usize, usize, i64) {
    let (s, q) = (*p, (b[*p] == b'"') as usize);
    let (mut i, mut pairs) = (s + q, 0);
    loop {
        i += b[i..].iter().position(|&c| c == [b',', b'"'][q]).unwrap();
        if q == 0 || b[i + 1] != b'"' {
            break;
        }
        (i, pairs) = (i + 2, pairs + 1); // a "" escape
    }
    *p = i + 1 + q;
    (s + q, i, (i - s - q - pairs) as i64)
}

/// Parses `-?[0-9.]+` as an integer, skipping the dot (so an amount comes out in cents),
/// then steps past the delimiter after it: a comma, LF or CRLF.
fn number(b: &[u8], p: &mut usize) -> i64 {
    let (neg, mut v) = (b[*p] == b'-', 0);
    *p += neg as usize;
    while let Some(&c @ (b'0'..=b'9' | b'.')) = b.get(*p) {
        *p += 1;
        if c != b'.' {
            v = v * 10 + (c - b'0') as i64;
        }
    }
    *p += 1 + (b.get(*p) == Some(&b'\r')) as usize;
    [v, -v][neg as usize]
}

/// The first record start at or after `p`, given the number of quotes before `p`: the byte
/// after the first LF outside quotes, i.e. with an even number of quotes before it.
fn sync(b: &[u8], mut p: usize, mut quotes: usize) -> usize {
    while p < b.len() && (b[p] != b'\n' || quotes % 2 == 1) {
        quotes += (b[p] == b'"') as usize;
        p += 1;
    }
    b.len().min(p + 1)
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

fn main() {
    let dir = |k, d: &str| env::var(k).unwrap_or(d.into());
    let (data, out) = (dir("SD_DATA", "/data"), dir("SD_OUT", "/out"));
    let recs = map(format!("{data}/records.csv"));
    let regs = map(format!("{data}/regions.csv"));
    // Split the records after the header into 16 chunks per thread. Counting quotes tells
    // each chunk's quote parity, so a chunk can move its start to a true record boundary:
    // an LF outside quotes. One more thread reads the regions meanwhile.
    let start = recs.iter().position(|&c| c == b'\n').unwrap() + 1;
    let n = thread::available_parallelism().map_or(1, |n| n.get());
    let chunks = 16 * n;
    let cut = |c: usize| start + (recs.len() - start) * c / chunks;
    let count = |b: &[u8]| b.iter().fold(0u8, |a, &c| a + (c == b'"') as u8) as usize;
    // Chunks go to whichever thread is free (see `claim`).
    let (quotes, region, mut keys) = thread::scope(|s| {
        let regions = s.spawn(|| {
            // region -> group, and country code (as a number below 26^3) -> group
            let (mut region, mut group, mut keys) = (vec![], vec![u8::MAX; 17576], vec![]);
            for line in regs.split_inclusive(|&c| c == b'\n').skip(1) {
                let mut p = 0;
                let id = number(line, &mut p) as usize;
                let code = line[p..p + 3]
                    .iter()
                    .fold(0, |a, &c| a * 26 + (c - b'A') as usize);
                if group[code] == u8::MAX {
                    assert!(keys.len() < 255, "at most 255 countries");
                    group[code] = keys.len() as u8;
                    keys.push(&line[p..p + 3]);
                }
                region.resize(region.len().max(id + 1), u8::MAX);
                region[id] = group[code];
            }
            (region, keys)
        });
        // Thread t counts chunks t, t + n, ...; sums of u8 counts vectorize best.
        let quotes = par(n, |t| {
            let q = |c: usize| recs[cut(c)..cut(c + 1)].chunks(255).map(count).sum();
            (t..chunks).step_by(n).map(q).collect::<Vec<usize>>()
        });
        let (region, keys) = regions.join().unwrap();
        (quotes, region, keys)
    });
    let mut before = vec![0; chunks]; // quotes before each chunk
    (1..chunks).for_each(|c| before[c] = before[c - 1] + quotes[(c - 1) % n][(c - 1) / n]);
    let bound = |c: usize| match c {
        0 => start,
        _ if c == chunks => recs.len(),
        _ => sync(recs, cut(c), before[c]),
    };
    let unmatched = keys.len();
    keys.push(&b"_UNMATCHED"[..]);
    let mut bits = 17; // 2^17 slots; four times as many whenever 7/8 of them fill up
    let aggs = loop {
        let (names, next) = (Names::new(bits), AtomicUsize::new(0));
        let aggs = par(n, |_| {
            // A record is finished (its group and name looked up) while the next one is
            // parsed, so that the cache lines it needs have time to arrive.
            let (mut agg, mut last) = (vec![EMPTY; unmatched + 1], None);
            let mut finish = |(key, rid, mut rec): (_, usize, Agg)| {
                let g = unmatched.min(*region.get(rid).unwrap_or(&u8::MAX) as usize);
                rec[5] = names.see(key, g);
                merge(&mut agg[g], rec);
            };
            let claim = || Some(next.fetch_add(1, Relaxed)).filter(|&c| c < chunks);
            while let Some(c) = claim() {
                let (mut p, end) = (bound(c), bound(c + 1));
                while p < end {
                    p += 3 * recs[p..].starts_with(b"\xEF\xBB\xBF") as usize; // a byte order mark
                    let id = number(recs, &mut p);
                    let ((s, e, name_len), (_, _, note_len)) =
                        (field(recs, &mut p), field(recs, &mut p));
                    let rid = number(recs, &mut p) as usize;
                    region.get(rid).map(prefetch);
                    let cents = number(recs, &mut p);
                    let rec = [1, id, cents, cents, cents, 0, name_len, note_len];
                    last.replace((names.key(recs, s, e), rid, rec))
                        .map(&mut finish);
                }
            }
            last.take().map(&mut finish);
            agg
        });
        if !names.full() {
            break aggs;
        }
        bits += 2;
    };
    let mut lines: Vec<String> = Vec::new();
    for (g, key) in keys.iter().enumerate() {
        let mut a = EMPTY;
        aggs.iter().for_each(|agg| merge(&mut a, agg[g]));
        if a[0] > 0 {
            let cols: String = a.iter().enumerate().map(|(i, &v)| column(i, v)).collect();
            lines.push(format!("{}{cols}\n", String::from_utf8_lossy(key)));
        }
    }
    lines.sort(); // by key, since a key is followed by a space, which sorts before [A-Z_]
    fs::create_dir_all(&out).unwrap();
    fs::write(format!("{out}/aggregates.txt"), lines.concat()).unwrap();
}
