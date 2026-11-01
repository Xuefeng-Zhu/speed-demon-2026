//! Speed Demon 2026, Track B (Index). Standard library only.
//!
//! 1. Parse the queries and intern every term they use. From a small sample
//!    of the corpus: frequent BOOL terms get a bitmap over all documents, the
//!    others posting lists; each phrase is anchored on its rarest term.
//! 2. Map docs.txt and cut it into chunks of whole lines, each starting at a
//!    multiple of 64 documents, claimed by the threads in turn. A thread
//!    tokenizes its chunk once: it sets the bitmap bits (the chunk owns whole
//!    words of them), builds u16 posting lists local to the chunk, and checks
//!    the phrases around each anchor occurrence.
//! 3. The threads then answer blocks of queries. A BOOL query runs left to
//!    right on a sorted list, switching to a bitmap when a large set is ORed in.

use std::fmt::Write as _;
use std::sync::atomic::{AtomicU64, AtomicUsize, Ordering::Relaxed};
use std::{collections::HashMap, env, fs, thread};

/// Bytes of corpus read up front to estimate which phrase term is rarest.
const SAMPLE: usize = 1 << 19;
/// Bytes of corpus a thread scans between releasing what it has read.
const SLICE: usize = 1 << 20;
/// Bits in the filter of the short query terms' hashes.
const FILTER: usize = 1 << 20;
/// Term roles: used by a BOOL query and gets a posting list; anchors a
/// phrase; used by a BOOL query and common, so it gets a bitmap instead.
const IN_BOOL: u8 = 1;
const ANCHOR: u8 = 2;
const BITMAP: u8 = 4;

/// ONES[16 - n..32 - n] masks the first n of 16 bytes.
const ONES: [u8; 32] = *b"\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0";

/// The first 16 bytes of the n-byte token at data[s..], zero-padded; tokens
/// never contain a zero byte. Token bytes are ASCII letters and digits, so
/// OR-ing 0x20 lowercases letters and leaves digits alone.
fn key(data: &[u8], s: usize, n: usize) -> [u64; 2] {
    let mut pad = [0u8; 16];
    let src = data.get(s..s + 16).unwrap_or_else(|| {
        pad[..n.min(16)].copy_from_slice(&data[s..s + n.min(16)]);
        &pad
    });
    let x = u128::from_le_bytes(src[..16].try_into().unwrap()) | u128::from_le_bytes([0x20; 16]);
    let x = x & u128::from_le_bytes(ONES[16 - n.min(16)..][..16].try_into().unwrap());
    [x as u64, (x >> 64) as u64]
}

/// The queries and their terms: an open-addressing table from the key of a
/// term of at most 16 bytes to its id, a map for longer terms, and what the
/// corpus scan does with each term: its roles, and the phrases it anchors,
/// anchors[aoff[t]..aoff[t + 1]] for term t, as (query, start of the phrase
/// in `flat`, its length, position of the term in it). The list terms
/// (IN_BOOL) are 0..nlist, nlist <= 65,535, so their ids fit a u16; the
/// BITMAP terms follow, term nlist + i with bitmap i of nbm. Bit h % FILTER
/// of `filter` is set for each hash h of a short term in the table.
#[derive(Default)]
struct Plan {
    keys: Vec<[u64; 3]>,
    filter: Vec<u64>,
    empty: usize,
    long: HashMap<Vec<u8>, u32>,
    role: Vec<u8>,
    aoff: Vec<u32>,
    anchors: Vec<(u32, u32, u32, u32)>,
    flat: Vec<u32>,
    nlist: usize,
    nbm: usize,
    chunks: Vec<Chunk>,
    rows: Vec<u64>,
}

impl Plan {
    /// The 24-bit hash of the key k; its low bits are the home slot.
    fn hash(k: [u64; 2]) -> usize {
        ((k[0] ^ k[1].rotate_left(29)).wrapping_mul(0x9e37_79b9_7f4a_7c15) >> 40) as usize
    }

    /// The home slot of the key k.
    fn home(&self, k: [u64; 2]) -> usize {
        Self::hash(k) & (self.keys.len() - 1)
    }

    /// The slot of the key k, probing from its home slot h: k or empty.
    fn slot(&self, k: [u64; 2], h: usize) -> usize {
        let mask = self.keys.len() - 1;
        let hit = |&i: &usize| self.keys[i][..2] == k || self.keys[i][0] == 0;
        (h..).map(|i| i & mask).find(hit).unwrap()
    }

    /// The id of the term w = data[s..e], added if new, after adding `role` to its roles.
    fn intern(&mut self, data: &[u8], s: usize, e: usize, role: u8) -> u32 {
        let (w, k, t) = (&data[s..e], key(data, s, e - s), self.role.len() as u32);
        let t = if w.len() > 16 {
            *self.long.entry(w.to_vec()).or_insert(t)
        } else {
            let i = self.slot(k, self.home(k));
            if self.keys[i][0] == 0 {
                self.keys[i] = [k[0], k[1], t as u64];
            }
            self.keys[i][2] as u32
        };
        if t as usize == self.role.len() {
            self.role.push(0);
            if t as usize * 3 >= self.keys.len() * 2 {
                self.grow(self.keys.len() * 2); // at most two thirds full
            }
        }
        self.role[t as usize] |= role;
        t
    }

    /// Rebuilds the table with n slots.
    fn grow(&mut self, n: usize) {
        let old = std::mem::replace(&mut self.keys, vec![[0; 3]; n]);
        for e in old.into_iter().filter(|e| e[0] != 0) {
            let i = self.slot([e[0], e[1]], self.home([e[0], e[1]]));
            self.keys[i] = e;
        }
    }
}

/// Calls `f` with the term ids (the last id for a token no query uses) of
/// each document in data[lo..hi], which must be whole lines. Pages are released
/// as the scan passes them, so only a few of them stay resident.
fn for_each_doc(data: &[u8], lo: usize, hi: usize, plan: &Plan, mut f: impl FnMut(&[u32])) {
    let (mut i, mut done, mut tokens, mut keys) = (lo, lo, Vec::new(), Vec::new());
    while i < hi {
        i += data[i..].iter().position(|&b| b == b'\t').unwrap() + 1;
        // Key every token and prefetch its slot, then look them all up, so
        // that many cache misses are in flight at once. A short token whose
        // filter bit is clear is no query term: it is looked up as the empty
        // key at an empty slot, which matches at once (measured faster than
        // probing that slot with the real key). Branch-free: `miss` is all ones
        // for such a token.
        i = each_token(data, i, |s, e| {
            let k = key(data, s, e - s);
            let f = Plan::hash(k) % FILTER;
            let miss = ((e - s <= 16) as u64 & !plan.filter[f / 64] >> f % 64 & 1).wrapping_neg();
            let h = if e - s <= 16 { plan.home(k) } else { !(e - s) };
            let (k, h) = (k.map(|x| x & !miss), h ^ (h ^ plan.empty) & miss as usize);
            _ = plan.keys.get(h).map(prefetch);
            keys.push((k, h, s));
        });
        let none = plan.role.len() as u32 - 1;
        let long = |w: &[u8]| *plan.long.get(&w.to_ascii_lowercase()).unwrap_or(&none);
        tokens.extend(keys.iter().map(|&(k, h, s)| match plan.keys.get(h) {
            Some(_) => plan.keys[plan.slot(k, h)][2] as u32,
            None => long(&data[s..s + !h]),
        }));
        f(&tokens);
        tokens.clear();
        keys.clear();
        if i - done >= SLICE || i >= hi {
            release(&data[done..i]);
            done = i;
        }
    }
}

/// Calls f(s, e) for each token data[s..e] of the line from byte i, and returns
/// the start of the next line (or a position past the end of data). The bounds
/// come from masks of 64 bytes at a time; bit p of `after`: byte p - 1 is in a token.
fn each_token(data: &[u8], mut i: usize, mut f: impl FnMut(usize, usize)) -> usize {
    let (mut carry, mut open) = (0, 0);
    loop {
        let (m, lf) = masks(data, i);
        let m = m & (lf & lf.wrapping_neg()).wrapping_sub(1);
        let after = m << 1 | carry;
        let (mut starts, mut ends) = (m & !after, !m & after);
        while ends != 0 {
            let e = i + ends.trailing_zeros() as usize;
            let start = i + starts.trailing_zeros() as usize;
            let s = if carry != 0 { open } else { start };
            carry = 0;
            starts &= starts.wrapping_sub((s >= i) as u64);
            ends &= ends - 1;
            f(s, e);
        }
        // A token that runs on into the next 64 bytes.
        if starts != 0 {
            open = i + starts.trailing_zeros() as usize;
        }
        carry = m >> 63;
        i += (lf.trailing_zeros() as usize + 1).min(64);
        if lf != 0 || i >= data.len() {
            return i;
        }
    }
}

/// Bit masks of the token bytes (spec 2.2) and of the LFs in data[i..i + 64].
fn masks(data: &[u8], i: usize) -> (u64, u64) {
    let mut pad = [0u8; 64];
    let b: &[u8; 64] = match data.get(i..i + 64) {
        Some(b) => b.try_into().unwrap(),
        None => {
            pad[..data.len() - i].copy_from_slice(&data[i..]);
            &pad
        }
    };
    #[cfg(target_feature = "avx2")]
    unsafe {
        use std::arch::x86_64::*;
        let half = |h: usize| {
            let v = _mm256_loadu_si256(b.as_ptr().add(32 * h).cast());
            // Unsigned x - lo < n, as min(x - lo, n - 1) == x - lo.
            let within = |x, lo: u8, n: u8| {
                let d = _mm256_sub_epi8(x, _mm256_set1_epi8(lo as i8));
                _mm256_cmpeq_epi8(_mm256_min_epu8(d, _mm256_set1_epi8(n as i8 - 1)), d)
            };
            let low = _mm256_or_si256(v, _mm256_set1_epi8(0x20));
            let tok = _mm256_or_si256(within(low, b'a', 26), within(v, b'0', 10));
            let lf = _mm256_cmpeq_epi8(v, _mm256_set1_epi8(b'\n' as i8));
            let bits = |x| _mm256_movemask_epi8(x) as u32 as u64;
            (bits(tok), bits(lf))
        };
        let ((m0, l0), (m1, l1)) = (half(0), half(1));
        (m0 | m1 << 32, l0 | l1 << 32)
    }
    #[cfg(not(target_feature = "avx2"))]
    {
        let (mut m, mut lf) = (0u64, 0u64);
        for (j, &c) in b.iter().enumerate() {
            let tok = (c | 0x20).wrapping_sub(b'a') < 26 || c.wrapping_sub(b'0') < 10;
            m |= (tok as u64) << j;
            lf |= ((c == b'\n') as u64) << j;
        }
        (m, lf)
    }
}

/// Asks the CPU to start loading the cache line of `p`.
fn prefetch<T>(p: &T) {
    #[cfg(target_arch = "x86_64")]
    unsafe {
        use std::arch::x86_64::{_mm_prefetch, _MM_HINT_T0};
        _mm_prefetch::<_MM_HINT_T0>(p as *const T as *const i8)
    };
    #[cfg(target_arch = "aarch64")]
    unsafe {
        std::arch::asm!("prfm pldl1keep, [{0}]", in(reg) p, options(nostack, readonly, preserves_flags))
    };
}

/// A chunk's posting lists: list l has the ids first + docs[offs[l]..offs[l + 1]],
/// and its phrase matches as (query, id).
struct Chunk {
    first: u32,
    offs: Vec<u32>,
    docs: Vec<u16>,
    hits: Vec<(u32, u32)>,
}

impl Chunk {
    /// The chunk-local ids of the documents in list l.
    fn post(&self, l: usize) -> &[u16] {
        &self.docs[self.offs[l] as usize..self.offs[l + 1] as usize]
    }
}

/// Indexes the whole lines in data[lo..hi]; their first id is a multiple of 64,
/// so the chunk owns whole words of the shared bitmap rows.
fn scan_chunk(data: &[u8], lo: usize, hi: usize, plan: &Plan, rows: &[AtomicU64]) -> Chunk {
    let first = id_at(data, lo);
    let (nl, words) = (plan.nlist, rows.len() / plan.nbm.max(1));
    // The list-term ids of each document, each document ended by u16::MAX.
    let mut stream = Vec::with_capacity((hi - lo) / 16);
    let (mut hits, mut doc, mut new, mut anch) = (Vec::new(), first, Vec::new(), Vec::new());
    // The bitmap words of the current 64 documents, stored when they are done.
    let mut group = vec![0u64; plan.nbm + 1]; // and one for all other terms
    let flush = |group: &mut [u64], doc: u32| {
        for (b, x) in group[..plan.nbm].iter_mut().enumerate() {
            rows[b * words + doc as usize / 64].store(std::mem::take(x), Relaxed);
        }
    };
    for_each_doc(data, lo, hi, plan, |tokens| {
        if doc % 64 == 0 && doc != first {
            flush(&mut group, doc - 1);
        }
        // Branch-free: write every term, keep the list terms and note the
        // anchors; a term without a bitmap sets a bit in the spare group word.
        new.resize(tokens.len(), 0);
        anch.resize(tokens.len(), 0);
        let (mut n, mut m) = (0, 0);
        let bit = 1u64 << (doc & 63);
        for (p, &t) in tokens.iter().enumerate() {
            (new[n], anch[m]) = (t as u16, p);
            n += ((t as usize) < nl) as usize;
            m += (plan.role[t as usize] & ANCHOR != 0) as usize;
            group[(t as usize).wrapping_sub(nl).min(plan.nbm)] |= bit;
        }
        stream.extend_from_slice(&new[..n]);
        stream.push(u16::MAX);
        // Phrases: compare the tokens around each anchor with its phrases,
        // after prefetching what that reads, a level for all anchors at a time.
        let (anch, term) = (&anch[..m], |p: &usize| tokens[*p] as usize);
        let ranges = |p: &usize| plan.aoff[term(p)] as usize..plan.aoff[term(p) + 1] as usize;
        anch.iter().for_each(|p| prefetch(&plan.aoff[term(p)]));
        for p in anch {
            _ = plan.anchors.get(ranges(p).start).map(prefetch);
        }
        for a in anch.iter().flat_map(ranges) {
            prefetch(&plan.flat[plan.anchors[a].1 as usize]);
        }
        for &p in anch {
            for &(q, s, n, j) in &plan.anchors[ranges(&p)] {
                let (s, n, j) = (s as usize, n as usize, j as usize);
                if p >= j && tokens.get(p - j..p - j + n) == Some(&plan.flat[s..s + n]) {
                    hits.push((q, doc));
                }
            }
        }
        doc += 1;
    });
    if doc != first {
        flush(&mut group, doc - 1);
    }
    assert!(doc - first <= 1 << 16, "chunk too large");
    // Counting sort of the stream. offs[l + 2] counts list l, then offs[l + 1] is
    // where its next id goes, and after the fill offs[l] is where list l starts.
    let mut offs = vec![0u32; nl + 2];
    for &l in stream.iter().filter(|&&l| l != u16::MAX) {
        offs[l as usize + 2] += 1;
    }
    (2..offs.len()).for_each(|l| offs[l] += offs[l - 1]);
    let (mut docs, mut d) = (vec![0u16; offs[nl + 1] as usize], 0u16);
    for l in stream {
        if l == u16::MAX {
            d = d.wrapping_add(1);
        } else {
            let e = &mut offs[l as usize + 1];
            docs[*e as usize] = d;
            *e += 1;
        }
    }
    // Drop a term's repeats within a document: equal neighbours in its list.
    let mut w = 0;
    for l in 0..nl {
        let (a, b) = (offs[l] as usize, offs[l + 1] as usize);
        offs[l] = w as u32;
        for i in a..b {
            let keep = i == a || docs[i] != docs[i - 1];
            docs[w] = docs[i];
            w += keep as usize;
        }
    }
    offs[nl] = w as u32;
    Chunk { first, offs, docs, hits }
}

/// Appends a query's answer line: the count, the id sum and the first ten ids.
fn line(out: &mut String, n: usize, sum: u64, top: impl Iterator<Item = u32>) {
    write!(out, "{n} {sum}").unwrap();
    top.take(10).for_each(|d| write!(out, " {d}").unwrap());
    out.push('\n');
}

/// Appends the answer line of the ids in d, which are sorted.
fn sorted_line(out: &mut String, d: impl ExactSizeIterator<Item = u32> + Clone) {
    line(out, d.len(), d.clone().map(u64::from).sum(), d)
}

/// Answers a BOOL query strictly left to right. The running result is a sorted
/// list `r` until a large set is ORed in, then the bitmap `bm`, which is all
/// zero whenever it is not in use.
fn boolean(q: &[(u8, u32)], plan: &Plan, s: &mut Scratch, out: &mut String) {
    let (chunks, rows) = (&plan.chunks, &plan.rows);
    let words = s.bm.len();
    let (mut is_bm, r, bm, tl) = (false, &mut s.list, &mut s.bm, &mut s.tmp);
    r.clear();
    let get = |b: &[u64], d: u32| b[d as usize / 64] >> (d & 63) & 1 != 0;
    let set = |b: &mut [u64], d: u32| b[d as usize / 64] |= 1 << (d & 63);
    let clear = |b: &mut [u64], d: u32| b[d as usize / 64] &= !(1 << (d & 63));
    for &(op, t) in q {
        let t = t as usize;
        let and = op == b'A';
        if plan.role[t] & BITMAP != 0 {
            let row = &rows[(t - plan.nlist) * words..][..words];
            match (is_bm, op) {
                (false, b'A' | b'N') => r.retain(|&d| get(row, d) == and),
                (false, _) => {
                    bm.copy_from_slice(row);
                    r.drain(..).for_each(|d| set(bm, d));
                    is_bm = true;
                }
                (true, b'A') => bm.iter_mut().zip(row).for_each(|(x, y)| *x &= y),
                (true, b'N') => bm.iter_mut().zip(row).for_each(|(x, y)| *x &= !y),
                _ => bm.iter_mut().zip(row).for_each(|(x, y)| *x |= y),
            }
            continue;
        }
        let df: usize = chunks.iter().map(|c| c.post(t).len()).sum();
        if !is_bm && (and || op == b'N') && r.len() * 16 < df {
            // Look the few ids of r up in the term's lists.
            let has = |d: u32| {
                let c = &chunks[chunks.partition_point(|c| c.first <= d) - 1];
                c.post(t).binary_search(&((d - c.first) as u16)).is_ok()
            };
            r.retain(|&d| has(d) == and);
            continue;
        }
        tl.clear();
        for c in chunks {
            tl.extend(c.post(t).iter().map(|&d| c.first + d as u32));
        }
        if !is_bm && op == b'O' && r.len() + tl.len() > words / 4 {
            r.drain(..).for_each(|d| set(bm, d));
            is_bm = true;
        }
        match (is_bm, op) {
            (true, b'A') => {
                r.extend(tl.iter().filter(|&&d| get(bm, d)));
                bm.fill(0);
                is_bm = false;
            }
            (true, b'N') => tl.iter().for_each(|&d| clear(bm, d)),
            (true, _) => tl.iter().for_each(|&d| set(bm, d)),
            (false, b'A') if tl.len() * 16 < r.len() => {
                tl.retain(|d| r.binary_search(d).is_ok());
                std::mem::swap(r, tl);
            }
            (false, b'A' | b'N') => {
                tl.iter().for_each(|&d| set(bm, d));
                r.retain(|&d| get(bm, d) == and);
                tl.iter().for_each(|&d| bm[d as usize / 64] = 0);
            }
            _ => {
                // Merge the sorted lists r and tl.
                let (mut i, mut j, o) = (0, 0, &mut s.out);
                o.clear();
                while i < r.len() && j < tl.len() {
                    let (a, b) = (r[i], tl[j]);
                    o.push(a.min(b));
                    i += (a <= b) as usize;
                    j += (b <= a) as usize;
                }
                o.extend_from_slice(&r[i..]);
                o.extend_from_slice(&tl[j..]);
                std::mem::swap(r, o);
            }
        }
    }
    if !is_bm {
        return sorted_line(out, r.iter().copied());
    }
    // Count, id sum and the first ten ids. The positions of the set bits of x
    // sum to the sum over k of 2^k times the count of those with bit k.
    let (mut n, mut sum) = (0, 0);
    for (i, &x) in bm.iter().enumerate() {
        let pos = (0..6).map(|k| ((x & !(!0 / ((1 << (1 << k)) + 1))).count_ones() as u64) << k);
        n += x.count_ones() as usize;
        sum += (i * 64) as u64 * x.count_ones() as u64 + pos.sum::<u64>();
    }
    let ids = bm.iter().enumerate().filter(|(_, &x)| x != 0);
    let bits = |x: u64| (0..64).filter(move |b| x >> b & 1 != 0);
    let ids = ids.flat_map(|(i, &x)| bits(x).map(move |b| (i * 64 + b) as u32));
    line(out, n, sum, ids);
    bm.fill(0);
}

/// Per-thread buffers for answering queries.
#[derive(Default)]
struct Scratch {
    list: Vec<u32>,
    tmp: Vec<u32>,
    out: Vec<u32>,
    bm: Vec<u64>,
}

/// The id of the line that starts at byte i.
fn id_at(data: &[u8], i: usize) -> u32 {
    if i >= data.len() {
        return u32::MAX; // an empty last chunk
    }
    let digits = data[i..].iter().take_while(|&&b| b != b'\t');
    digits.fold(0, |n, &b| n * 10 + (b - b'0') as u32)
}

// std has no mmap; libc is always linked.
extern "C" {
    fn mmap(addr: *mut u8, len: usize, prot: i32, flags: i32, fd: i32, off: i64) -> *mut u8;
    fn madvise(addr: *mut u8, len: usize, advice: i32) -> i32;
}

/// Maps a read-only file into memory.
fn map_file(path: &str) -> &'static [u8] {
    let f = fs::File::open(path).expect("open docs.txt");
    let len = f.metadata().unwrap().len() as usize;
    let fd = std::os::fd::AsRawFd::as_raw_fd(&f);
    // PROT_READ = 1, MAP_PRIVATE = 2 on Linux x86-64 and aarch64.
    let p = unsafe { mmap(std::ptr::null_mut(), len, 1, 2, fd, 0) };
    assert!(p as isize != -1, "mmap failed");
    unsafe { std::slice::from_raw_parts(p, len) }
}

/// Drops the whole pages inside `s` from this process's mapping of the file;
/// the page cache keeps them, so a later read just maps them again.
fn release(s: &[u8]) {
    let lo = (s.as_ptr() as usize).next_multiple_of(4096);
    let hi = (s.as_ptr() as usize + s.len()) & !4095;
    unsafe { madvise(lo as *mut u8, hi.saturating_sub(lo), 4) }; // MADV_DONTNEED
}

/// Runs f(0), ..., f(n - 1) on n threads and returns the results in order.
fn par<T: Send>(n: usize, f: impl Fn(usize) -> T + Sync) -> Vec<T> {
    let f = &f;
    thread::scope(|s| {
        let hs: Vec<_> = (0..n).map(|k| s.spawn(move || f(k))).collect();
        hs.into_iter().map(|h| h.join().unwrap()).collect()
    })
}

/// The start of the first line that begins at or after byte `i`.
fn line_start(data: &[u8], i: usize) -> usize {
    (i.min(data.len())..data.len())
        .find(|&j| j == 0 || data[j - 1] == b'\n')
        .unwrap_or(data.len())
}

fn main() {
    let data_dir = env::var("SD_DATA").unwrap_or_else(|_| "/data".into());
    let out_dir = env::var("SD_OUT").unwrap_or_else(|_| "/out".into());
    let nthreads = env::var("SD_THREADS").ok().and_then(|s| s.parse().ok());
    let nthreads = nthreads.unwrap_or_else(|| thread::available_parallelism().map_or(4, |n| n.get()));

    let qtext = fs::read(format!("{data_dir}/queries.txt")).expect("read queries.txt");
    let mut plan = Plan::default();
    plan.grow((qtext.len() / 16 | 64).next_power_of_two()); // rarely grows
    // Query words: BOOL and PHRASE start a query, AND, OR and NOT are
    // operators and terms are lowercase. Query i is (b'B' or b'P', its first
    // term), its terms terms[qs[i].1..qs[i + 1].1] as (first byte of the
    // operator: AND, NOT, else OR; term); the first term of a BOOL query has
    // operator 0, OR on the empty set.
    let (mut qs, mut terms, mut i, mut op) = (Vec::new(), Vec::new(), 0, 0);
    while i < qtext.len() {
        i = each_token(&qtext, i, |s, e| match qtext[s] {
            b'B' | b'P' => qs.push((qtext[s], terms.len() as u32)),
            b'A' | b'O' | b'N' => op = qtext[s],
            _ => {
                let role = IN_BOOL * (qs[qs.len() - 1].0 == b'B') as u8;
                terms.push((std::mem::take(&mut op), plan.intern(&qtext, s, e, role)));
            }
        });
    }
    let nq = qs.len();
    qs.push((0, terms.len() as u32));
    let data = map_file(&format!("{data_dir}/docs.txt"));

    // Anchor each phrase on its rarest term in a sample of the corpus.
    // The id of every token no query uses: a term with no role.
    let none = plan.role.len() as u32;
    plan.filter = vec![0; FILTER / 64];
    plan.empty = plan.keys.iter().position(|e| e[0] == 0).unwrap();
    for e in &mut plan.keys {
        let f = Plan::hash([e[0], e[1]]) % FILTER;
        plan.filter[f / 64] |= ((e[0] != 0) as u64) << (f % 64);
        e[2] = if e[0] == 0 { none as u64 } else { e[2] };
    }
    plan.role.push(0);
    // freq[t]: (sample documents with the term t, the last of them).
    let (mut freq, mut sdocs) = (vec![(0u32, 0u32); plan.role.len()], 0);
    for_each_doc(data, 0, line_start(data, SAMPLE), &plan, |tokens| {
        sdocs += 1;
        for &t in tokens {
            let f = &mut freq[t as usize];
            *f = (f.0 + (f.1 != sdocs) as u32, sdocs);
        }
    });
    // A BOOL term in more than 1 of 32 sample documents gets a bitmap,
    // and so do the most frequent others beyond 65,535.
    let mut bools: Vec<usize> = (0..plan.role.len()).filter(|&t| plan.role[t] & IN_BOOL != 0).collect();
    bools.sort_unstable_by_key(|&t| std::cmp::Reverse(freq[t].0));
    let common = bools.partition_point(|&t| freq[t].0 as usize * 32 > sdocs as usize);
    let nbm = common.max(bools.len().saturating_sub(65535));
    bools[..nbm].iter().for_each(|&t| plan.role[t] ^= IN_BOOL | BITMAP);
    (plan.nlist, plan.nbm) = (bools.len() - nbm, nbm);
    // Renumber the terms: list terms first, then bitmap terms, then the rest.
    let rest = (0..plan.role.len()).filter(|&t| plan.role[t] & (IN_BOOL | BITMAP) == 0);
    let mut order = [&bools[nbm..], &bools[..nbm]].concat();
    order.extend(rest);
    let mut new = vec![0; order.len()];
    for (i, &t) in order.iter().enumerate() {
        new[t] = i as u32;
    }
    plan.keys.iter_mut().for_each(|e| e[2] = new[e[2] as usize] as u64);
    plan.long.values_mut().for_each(|t| *t = new[*t as usize]);
    plan.role = order.iter().map(|&t| plan.role[t]).collect();
    let df: Vec<u32> = order.iter().map(|&t| freq[t].0).collect();
    terms.iter_mut().for_each(|e| e.1 = new[e.1 as usize]);
    let query = |i: usize| (qs[i].0, &terms[qs[i].1 as usize..qs[i + 1].1 as usize]);
    let mut list = Vec::new();
    for qi in (0..nq).filter(|&i| qs[i].0 == b'P') {
        let p = query(qi).1;
        let j = (0..p.len()).min_by_key(|&j| df[p[j].1 as usize]).unwrap();
        plan.role[p[j].1 as usize] |= ANCHOR;
        list.push((p[j].1, qi, p, j));
    }
    drop((qtext, freq, bools, order, new, df)); // the scan uses none of these
    // One flat list of anchors, grouped by term, with copies of the phrases.
    list.sort_unstable_by_key(|a| a.0);
    plan.aoff = vec![0; plan.role.len() + 1];
    list.iter().for_each(|a| plan.aoff[a.0 as usize + 1] += 1);
    (1..plan.aoff.len()).for_each(|t| plan.aoff[t] += plan.aoff[t - 1]);
    for (_, qi, p, j) in list {
        plan.anchors
            .push((qi as u32, plan.flat.len() as u32, p.len() as u32, j as u32));
        plan.flat.extend(p.iter().map(|e| e.1));
    }

    // Equal byte ranges, each moved to the next line whose id is a multiple
    // of 64; at most 65,536 lines per chunk.
    let last = data.rsplit(|&b| b == b'\n').nth(1); // the last line
    let ndocs = last.map_or(0, |l| id_at(l, 0) as usize + 1);
    let words = ndocs.div_ceil(64);
    // Zeroed pages straight from the OS, touched first by the scanning threads.
    let mut rows = std::mem::ManuallyDrop::new(vec![0u64; plan.nbm * words]);
    // Huge pages, each first written here: racing first faults each charge 2 MiB.
    let huge = |p: usize| (rows.as_ptr() as usize + p) & !((1 << 21) - 1);
    let (a, b) = (huge((1 << 21) - 1), huge(rows.len() * 8));
    if a < b {
        unsafe { madvise(a as *mut u8, b - a, 14) };
        (a..b).step_by(1 << 21).for_each(|p| unsafe { (p as *mut u8).write_volatile(0) });
    }
    // SAFETY: AtomicU64 has the size, alignment and bit validity of u64.
    let rows: Vec<AtomicU64> = unsafe { Vec::from_raw_parts(rows.as_mut_ptr().cast(), rows.len(), rows.capacity()) };
    let nchunks = nthreads * data.len().div_ceil(nthreads << 24).max(1);
    let cut = |k| {
        let mut i = line_start(data, k * data.len() / nchunks);
        while i < data.len() && id_at(data, i) % 64 != 0 {
            i = line_start(data, i + 1);
        }
        i
    };
    let next = AtomicUsize::new(0);
    let take = || next.fetch_add(1, Relaxed);
    let claim = |n| (0..).map(|_| take()).take_while(move |&k| k < n);
    let mut chunks: Vec<_> = par(nthreads, |_| {
        claim(nchunks).map(|k| (k, scan_chunk(data, cut(k), cut(k + 1), &plan, &rows))).collect::<Vec<_>>()
    })
    .into_iter()
    .flatten()
    .collect();
    chunks.sort_unstable_by_key(|c| c.0);
    plan.chunks = chunks.into_iter().map(|c| c.1).collect();
    plan.rows = rows.into_iter().map(AtomicU64::into_inner).collect();
    // The scan's tables; the answers do not use them.
    (plan.keys, plan.filter, plan.aoff, plan.anchors, plan.flat) = Default::default();
    // Phrase matches as sorted (query, id); a phrase can occur twice in a document.
    let mut hits = Vec::new();
    plan.chunks.iter().for_each(|c| hits.extend(&c.hits));
    hits.sort_unstable();
    hits.dedup();

    // Answer blocks of queries, claimed by the threads in turn.
    next.store(0, Relaxed);
    let block = 64;
    let mut outs: Vec<(usize, String)> = par(nthreads, |_| {
        let mut s = Scratch::default();
        s.bm = vec![0; words];
        claim(nq.div_ceil(block))
            .map(|b| {
                let mut out = String::new();
                for qi in b * block..((b + 1) * block).min(nq) {
                    match query(qi) {
                        (b'B', q) => boolean(q, &plan, &mut s, &mut out),
                        _ => {
                            let q = |h: &(u32, u32)| h.0 as usize;
                            let d = &hits[hits.partition_point(|h| q(h) < qi)..hits.partition_point(|h| q(h) <= qi)];
                            sorted_line(&mut out, d.iter().map(|h| h.1));
                        }
                    }
                }
                (b, out)
            })
            .collect::<Vec<_>>()
    })
    .into_iter()
    .flatten()
    .collect();
    outs.sort_unstable_by_key(|o| o.0);
    let out: String = outs.into_iter().map(|o| o.1).collect();
    fs::create_dir_all(&out_dir).ok();
    fs::write(format!("{out_dir}/results.txt"), out).expect("write results.txt");
    std::process::exit(0); // the OS frees everything faster than the destructors
}
