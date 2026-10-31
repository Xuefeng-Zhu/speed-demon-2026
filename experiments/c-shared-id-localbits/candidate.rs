//! Speed Demon 2026, Track C (Join): std-only Rust. README.md explains the design.
use std::collections::HashMap;
use std::hash::{BuildHasher, BuildHasherDefault, Hasher};
use std::{env, fs, os::fd::AsRawFd, sync::{Mutex, atomic::{AtomicUsize, Ordering}}, thread};

extern "C" {
    fn mmap(addr: *mut u8, len: usize, prot: i32, flags: i32, fd: i32, off: i64) -> *mut u8;
    fn memchr(s: *const u8, c: i32, n: usize) -> *const u8;
}

/// Maps a file read-only (PROT_READ, MAP_PRIVATE): its pages stay in the shared page cache.
fn map(path: String) -> &'static [u8] {
    let f = fs::File::open(&path).expect(&path);
    let len = f.metadata().unwrap().len() as usize;
    assert!(len > 0 && len <= isize::MAX as usize, "invalid input length: {path}");
    let ptr = unsafe { mmap(std::ptr::null_mut(), len, 1, 2, f.as_raw_fd(), 0) };
    if ptr as isize == -1 { panic!("mmap {path}: {}", std::io::Error::last_os_error()); }
    assert!(!ptr.is_null(), "null mmap pointer: {path}");
    unsafe { std::slice::from_raw_parts(ptr, len) }
}

/// Runs `f(0)..f(n - 1)` on n scoped threads and returns the results in order.
fn par<T: Send>(n: usize, f: impl Fn(usize) -> T + Sync) -> Vec<T> {
    let f = &f;
    thread::scope(|s| {
        let handles: Vec<_> = (0..n).map(|t| s.spawn(move || f(t))).collect();
        handles.into_iter().map(|h| h.join().unwrap()).collect()
    })
}

/// FxHash-style hasher, eight bytes per step: every record hashes its name twice.
#[derive(Default)]
struct Fx(u64);
impl Hasher for Fx {
    fn write(&mut self, s: &[u8]) {
        for c in s.chunks(8) {
            let w = c.iter().rev().fold(0, |w, &b| w << 8 | b as u64);
            self.0 = (self.0.rotate_left(5) ^ w).wrapping_mul(0x517cc1b727220a95);
        }
    }
    fn finish(&self) -> u64 {
        self.0 ^ self.0 >> 29
    }
}

/// Stable entries are never removed while workers run. Names borrow the mapped input.
struct Entry { name: &'static [u8], id: usize }
#[derive(Default)]
#[repr(align(128))]
struct Shard(Mutex<HashMap<&'static [u8], Box<Entry>, BuildHasherDefault<Fx>>>);
impl Shard {
    fn intern(&self, name: &'static [u8], next: &AtomicUsize) -> *const Entry {
        let mut map = self.0.lock().unwrap();
        if let Some(e) = map.get(name) { return &**e; }
        let entry = Box::new(Entry { name, id: next.fetch_add(1, Ordering::Relaxed) });
        let ptr = &*entry as *const Entry;
        map.insert(name, entry);
        ptr
    }
}

/// Parses the text field at `p` and steps past the comma after it. Returns the bytes
/// between the quotes, still escaped (escaping is one-to-one, so equal raw bytes mean
/// equal values, and unquoted text never contains a quote), and the unescaped length.
fn field(b: &'static [u8], p: &mut usize) -> (&'static [u8], i64) {
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
    (&b[s + q..i], (i - s - q - pairs) as i64)
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

/// Section 2.2 guarantees that every CR begins an outside-quote CRLF terminator.
fn sync_crlf(b: &[u8], p: usize) -> usize {
    if p >= b.len() { return b.len(); }
    let found = unsafe { memchr(b.as_ptr().add(p), b'\r' as i32, b.len() - p) };
    if found.is_null() { b.len() } else {
        let at = unsafe { found.offset_from(b.as_ptr()) as usize };
        debug_assert_eq!(b.get(at + 1), Some(&b'\n'));
        (at + 2).min(b.len())
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

fn main() {
    let dir = |k, d: &str| env::var(k).unwrap_or(d.into());
    let (data, out) = (dir("SD_DATA", "/data"), dir("SD_OUT", "/out"));
    let recs = map(format!("{data}/records.csv"));
    let regs = map(format!("{data}/regions.csv"));
    let (mut index, mut region) = (HashMap::new(), Vec::new()); // country -> group, region -> group
    for line in regs.split_inclusive(|&c| c == b'\n').skip(1) {
        let mut p = 0;
        let id = number(line, &mut p) as usize;
        let groups = index.len() as u16;
        region.resize(region.len().max(id + 1), u16::MAX);
        region[id] = *index.entry(&line[p..line.len() - 1]).or_insert(groups);
    }
    let unmatched = index.len();
    index.insert(b"_UNMATCHED", unmatched as u16);
    let words = (unmatched + 1).div_ceil(64);
    // Section 2.2 permits CRLF synchronization: every CR marks a record boundary,
    // including when a note contains bare LF. Repeated cuts may map to the same end.
    let start = recs.iter().position(|&c| c == b'\n').unwrap() + 1;
    let n = thread::available_parallelism().map_or(1, |n| n.get());
    let cut = |t: usize| start + (recs.len() - start) * t / n;
    let bound = |t: usize| match t {
        0 => start,
        _ if t == n => recs.len(),
        _ => sync_crlf(recs, cut(t)),
    };
    let names: Vec<Shard> = (0..1024).map(|_| Shard::default()).collect();
    let next = AtomicUsize::new(0);
    let aggs = par(n, |t| {
        let (mut p, end, mut agg) = (bound(t), bound(t + 1), vec![EMPTY; unmatched + 1]);
        let mut cache = vec![(0u64, std::ptr::null::<Entry>()); 1 << 18];
        let mut localbits: Vec<u64> = Vec::new();
        while p < end {
            p += 3 * recs[p..].starts_with(b"\xEF\xBB\xBF") as usize; // a byte order mark
            let id = number(recs, &mut p);
            let ((name, name_len), (_, note_len)) = (field(recs, &mut p), field(recs, &mut p));
            let rid = number(recs, &mut p) as usize;
            let g = unmatched.min(*region.get(rid).unwrap_or(&u16::MAX) as usize);
            let cents = number(recs, &mut p);
            let hash = BuildHasherDefault::<Fx>::default().hash_one(name);
            let slot = &mut cache[hash as usize & ((1 << 18) - 1)];
            // A pointer is installed only after interning under the shard mutex. Entries
            // stay allocated until after all workers and the reduction have joined.
            let hit = slot.0 == hash && !slot.1.is_null() && unsafe { (*slot.1).name == name };
            if !hit {
                slot.1 = names[(hash >> 32 & 1023) as usize].intern(name, &next);
                slot.0 = hash;
            }
            let row = unsafe { (*slot.1).id };
            let word = row * words + g / 64;
            if word >= localbits.len() { localbits.resize(word + 1, 0); }
            localbits[word] |= 1u64 << (g % 64);
            let new = 0;
            let rec = [1, id, cents, cents, cents, new, name_len, note_len];
            merge(&mut agg[g], rec);
        }
        (agg, localbits)
    });
    // OR per-worker occurrence bits. Partition by name so no row is double-counted.
    let count = next.load(Ordering::Relaxed);
    let distinct = par(n, |t| {
        let mut by_group = vec![0i64; unmatched + 1];
        for row in (count * t / n)..(count * (t + 1) / n) {
            for w in 0..words {
                let pos = row * words + w;
                let mut bits = 0u64;
                for (_, local) in &aggs { bits |= local.get(pos).copied().unwrap_or(0); }
                while bits != 0 {
                    let b = bits.trailing_zeros() as usize;
                    let g = w * 64 + b;
                    if g < by_group.len() { by_group[g] += 1; }
                    bits &= bits - 1;
                }
            }
        }
        by_group
    });
    let mut lines: Vec<String> = Vec::new();
    for (key, g) in index {
        let mut a = EMPTY;
        aggs.iter().for_each(|(agg, _)| merge(&mut a, agg[g as usize]));
        a[5] = distinct.iter().map(|d| d[g as usize]).sum();
        if a[0] > 0 {
            let cols: String = a.iter().enumerate().map(|(i, &v)| column(i, v)).collect();
            lines.push(format!("{}{cols}\n", String::from_utf8_lossy(key)));
        }
    }
    lines.sort(); // by key, since a key is followed by a space, which sorts before [A-Z_]
    fs::create_dir_all(&out).unwrap();
    fs::write(format!("{out}/aggregates.txt"), lines.concat()).unwrap();
}
