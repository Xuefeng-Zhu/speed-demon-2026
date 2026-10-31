//! Speed Demon 2026, Track C (Join): std-only Rust. README.md explains the design.
use std::collections::HashMap;
use std::hash::{BuildHasher, BuildHasherDefault, Hasher};
use std::{env, fs, os::fd::AsRawFd, sync::Mutex, thread};

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

/// One of 1024 shards of the shared name dictionary: name -> row, and per row a bitset of
/// the groups the name occurs in. Aligned so that no two shard locks share a cache line.
#[derive(Default)]
#[repr(align(128))]
struct Shard(Mutex<(HashMap<Box<[u8]>, usize, BuildHasherDefault<Fx>>, Vec<u64>)>);
impl Shard {
    /// Notes that `name` occurs in group `g`; returns 1 the first time, else 0.
    fn see(&self, name: &[u8], g: usize, words: usize) -> i64 {
        let (map, bits) = &mut *self.0.lock().unwrap();
        let row = match map.get(name) {
            Some(&row) => row,
            None => *map.entry(name.into()).or_insert(bits.len() / words),
        };
        bits.resize(bits.len().max((row + 1) * words), 0);
        let (w, bit) = (row * words + g / 64, 1 << (g % 64));
        let new = bits[w] & bit == 0;
        bits[w] |= bit;
        new as i64
    }
}

/// Find the first matching byte using guarded unaligned eight-byte loads.
#[inline(always)]
fn field_delim(b: &[u8], mut i: usize, c: u8) -> usize {
    let splat = u64::from(c).wrapping_mul(0x0101_0101_0101_0101);
    while b.len() - i >= 8 {
        let x = unsafe { u64::from_le(std::ptr::read_unaligned(b.as_ptr().add(i).cast::<u64>())) } ^ splat;
        let zeros = x.wrapping_sub(0x0101_0101_0101_0101) & !x & 0x8080_8080_8080_8080;
        if zeros != 0 { return i + (zeros.trailing_zeros() as usize / 8); }
        i += 8;
    }
    i + b[i..].iter().position(|&x| x == c).unwrap()
}

/// Parses the text field at `p` and steps past the comma after it. Returns the bytes
/// between the quotes, still escaped (escaping is one-to-one, so equal raw bytes mean
/// equal values, and unquoted text never contains a quote), and the unescaped length.
fn field(b: &'static [u8], p: &mut usize) -> (&'static [u8], i64) {
    let (s, q) = (*p, (b[*p] == b'"') as usize);
    let (mut i, mut pairs) = (s + q, 0);
    loop {
        i = field_delim(b, i, [b',', b'"'][q]);
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

/// Parse an unsigned comma-terminated id. Fast path handles up to seven digits;
/// guarded loads and scalar fallback cover all other legal lengths.
#[inline(always)]
fn positive_fast(b: &[u8], p: &mut usize) -> i64 {
    if b.len() - *p >= 8 {
        let raw = unsafe { u64::from_le(std::ptr::read_unaligned(b.as_ptr().add(*p).cast::<u64>())) };
        let x = raw ^ 0x2c2c_2c2c_2c2c_2c2c;
        let mask = x.wrapping_sub(0x0101_0101_0101_0101) & !x & 0x8080_8080_8080_8080;
        if mask != 0 {
            let n = mask.trailing_zeros() as usize / 8;
            if n > 0 {
                let mut v = raw.wrapping_shl(((8 - n) * 8) as u32) & 0x0f0f_0f0f_0f0f_0f0f;
                v = (v.wrapping_mul(10).wrapping_add(v >> 8)) & 0x00ff_00ff_00ff_00ff;
                v = (v.wrapping_mul(100).wrapping_add(v >> 16)) & 0x0000_ffff_0000_ffff;
                v = (v.wrapping_mul(10000).wrapping_add(v >> 32)) & 0x0000_0000_ffff_ffff;
                *p += n + 1;
                return v as i64;
            }
        }
    }
    number(b,p)
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
    // Country codes are exactly three uppercase ASCII bytes by §2.3.
    let mut code_group = vec![u16::MAX; 26 * 26 * 26];
    let (mut countries, mut region) = (Vec::<&[u8]>::new(), Vec::new());
    for line in regs.split_inclusive(|&c| c == b'\n').skip(1) {
        let mut p = 0;
        let id = number(line, &mut p) as usize;
        let code = &line[p..line.len() - 1];
        let k = usize::from(code[0] - b'A') * 676 + usize::from(code[1] - b'A') * 26 + usize::from(code[2] - b'A');
        let mut group = code_group[k];
        if group == u16::MAX {
            group = countries.len() as u16;
            code_group[k] = group;
            countries.push(code);
        }
        region.resize(region.len().max(id + 1), u16::MAX);
        region[id] = group;
    }
    let unmatched = countries.len();
    countries.push(b"_UNMATCHED");
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
    let aggs = par(n, |t| {
        let (mut p, end, mut agg) = (bound(t), bound(t + 1), vec![EMPTY; unmatched + 1]);
        while p < end {
            p += 3 * recs[p..].starts_with(b"\xEF\xBB\xBF") as usize; // a byte order mark
            let id = positive_fast(recs, &mut p);
            let ((name, name_len), (_, note_len)) = (field(recs, &mut p), field(recs, &mut p));
            let rid = positive_fast(recs, &mut p) as usize;
            let g = unmatched.min(*region.get(rid).unwrap_or(&u16::MAX) as usize);
            let cents = number(recs, &mut p);
            let shard = BuildHasherDefault::<Fx>::default().hash_one(name) >> 32 & 1023;
            let new = names[shard as usize].see(name, g, words);
            let rec = [1, id, cents, cents, cents, new, name_len, note_len];
            merge(&mut agg[g], rec);
        }
        agg
    });
    let mut lines: Vec<String> = Vec::new();
    for (g, key) in countries.into_iter().enumerate() {
        let mut a = EMPTY;
        aggs.iter().for_each(|agg| merge(&mut a, agg[g as usize]));
        if a[0] > 0 {
            let cols: String = a.iter().enumerate().map(|(i, &v)| column(i, v)).collect();
            lines.push(format!("{}{cols}\n", String::from_utf8_lossy(key)));
        }
    }
    lines.sort(); // by key, since a key is followed by a space, which sorts before [A-Z_]
    fs::create_dir_all(&out).unwrap();
    fs::write(format!("{out}/aggregates.txt"), lines.concat()).unwrap();
}
