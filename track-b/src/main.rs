//! Speed Demon 2026, Track B (Index). Standard library only.
//!
//! 1. Parse the queries and intern every term they use. From a small sample
//!    of the corpus: frequent BOOL terms get bitmaps, the others posting
//!    lists; each phrase is anchored on its rarest term.
//! 2. Map docs.txt and take it in blocks of up to 32,768 documents, so that
//!    only one block's index is in memory. All threads work on a block, then
//!    move on to the next together:
//!    - they tokenize its chunks, claimed in turn: set the bitmap bits (a
//!      chunk owns whole words of them), list the posting-list terms of each
//!      document, and check the phrases around each anchor occurrence;
//!    - they put the chunks' terms in the block's u16 posting lists;
//!    - they answer the BOOL queries that can match in the block, adding the
//!      count, id sum and first ids to each query's answer so far. A query
//!      runs left to right on a sorted list, switching to a bitmap when a large
//!      set is ORed in.

use std::fmt::Write as _;
use std::sync::atomic::{AtomicU16, AtomicU64, AtomicUsize, Ordering::Relaxed, Ordering::SeqCst};
use std::sync::{Mutex, RwLock};
use std::{collections::HashMap, env, fs, thread};

/// Bytes of corpus read up front to estimate which phrase term is rarest.
const SAMPLE: usize = 1 << 19;
/// Bytes of corpus a thread scans between releasing what it has read.
const SLICE: usize = 1 << 18;
/// Term roles: used by a BOOL query and gets a posting list; anchors a
/// phrase; used by a BOOL query and common, so it gets a bitmap instead.
const IN_BOOL: u8 = 1;
const ANCHOR: u8 = 2;
const BITMAP: u8 = 4;

/// The first 16 bytes of the n-byte token at data[s..], zero-padded; tokens
/// never contain a zero byte. Token bytes are ASCII letters and digits, so
/// OR-ing 0x20 lowercases letters and leaves digits alone.
fn key(data: &[u8], s: usize, n: usize) -> [u64; 2] {
    let mut pad = [0u8; 16];
    let src = data.get(s..s + 16).unwrap_or_else(|| {
        pad[..n.min(16)].copy_from_slice(&data[s..s + n.min(16)]);
        &pad
    });
    std::array::from_fn(|w| {
        let x = u64::from_le_bytes(src[w * 8..w * 8 + 8].try_into().unwrap());
        (x | 0x2020_2020_2020_2020) & ((1u128 << (n.saturating_sub(w * 8).min(8) * 8)) - 1) as u64
    })
}

/// The queries and their terms: an open-addressing table from the key of a
/// term of at most 16 bytes to its id, a map for longer terms, and what the
/// corpus scan does with each term: its roles, and the phrases it anchors,
/// anchors[aoff[t]..aoff[t + 1]] for term t, as (query, start of the phrase
/// in `flat`, its length, position of the term in it). The list terms
/// (IN_BOOL) are 0..nlist, nlist <= 65,535, so their ids fit a u16; the
/// BITMAP terms follow, term nlist + i with bitmap i of nbm.
#[derive(Default)]
struct Plan<'q> {
    queries: &'q [Query],
    keys: Vec<[u64; 3]>,
    long: HashMap<Vec<u8>, u32>,
    role: Vec<u8>,
    aoff: Vec<u32>,
    anchors: Vec<(u32, u32, u32, u32)>,
    flat: Vec<u32>,
    nlist: usize,
    nbm: usize,
}

impl Plan<'_> {
    /// The home slot of the key k.
    fn home(&self, k: [u64; 2]) -> usize {
        let h = (k[0] ^ k[1].rotate_left(29)).wrapping_mul(0x9e37_79b9_7f4a_7c15);
        (h >> 40) as usize & (self.keys.len() - 1)
    }

    /// The slot of the key k, probing from its home slot h: k or empty.
    fn slot(&self, k: [u64; 2], h: usize) -> usize {
        let mask = self.keys.len() - 1;
        (h..).map(|i| i & mask).find(|&i| self.keys[i][..2] == k || self.keys[i][0] == 0).unwrap()
    }

    /// The id of the term w, added if new, after adding `role` to its roles.
    fn intern(&mut self, w: &[u8], role: u8) -> u32 {
        let (k, t) = (key(w, 0, w.len()), self.role.len() as u32);
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
        // Where the tokens of the document start and end, from masks of 64
        // bytes at a time up to its LF. Bit p of `after`: byte p - 1 is in a
        // token. Key every token and prefetch its slot, then look them all
        // up, so that many cache misses are in flight at once.
        let (mut carry, mut open) = (0, 0);
        loop {
            let (m, lf) = masks(data, i);
            let m = m & (lf & lf.wrapping_neg()).wrapping_sub(1);
            let after = m << 1 | carry;
            let (mut starts, mut ends) = (m & !after, !m & after);
            while ends != 0 {
                let e = i + ends.trailing_zeros() as usize;
                let s = if carry != 0 { open } else { i + starts.trailing_zeros() as usize };
                (carry, starts, ends) = (0, starts & starts.wrapping_sub((s >= i) as u64), ends & (ends - 1));
                let k = key(data, s, e - s);
                let h = if e - s <= 16 { plan.home(k) } else { !(e - s) };
                _ = plan.keys.get(h).map(prefetch);
                keys.push((k, h, s));
            }
            // A token that runs on into the next 64 bytes.
            open = if starts != 0 { i + starts.trailing_zeros() as usize } else { open };
            carry = m >> 63;
            i += (lf.trailing_zeros() as usize + 1).min(64);
            if lf != 0 {
                break;
            }
        }
        let none = plan.role.len() as u32 - 1;
        tokens.extend(keys.iter().map(|&(k, h, s)| match plan.keys.get(h) {
            Some(_) => plan.keys[plan.slot(k, h)][2] as u32,
            None => {
                let t = data[s..s + !h].to_ascii_lowercase();
                plan.long.get(&t).copied().unwrap_or(none)
            }
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
            (_mm256_movemask_epi8(tok) as u32 as u64, _mm256_movemask_epi8(lf) as u32 as u64)
        };
        let ((m0, l0), (m1, l1)) = (half(0), half(1));
        (m0 | m1 << 32, l0 | l1 << 32)
    }
    #[cfg(not(target_feature = "avx2"))]
    {
        let (mut m, mut lf) = (0u64, 0u64);
        for j in 0..64 {
            let c = b[j];
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

/// Replaces each term t of the queries by new[t].
fn remap(queries: &mut [Query], new: &[u32]) {
    for q in queries {
        match q {
            Query::Bool(v) => v.iter_mut().for_each(|(_, t)| *t = new[*t as usize]),
            Query::Phrase(p) => p.iter_mut().for_each(|t| *t = new[*t as usize]),
        }
    }
}

enum Query {
    Bool(Vec<(u8, u32)>), // (first byte of the operator: AND, NOT, else OR; term)
    Phrase(Vec<u32>),
}

/// A chunk: the list-term ids of its documents, first one after the other,
/// each document ended by u16::MAX and a term's repeats dropped; the number
/// of documents in each list; its phrase matches as (query, id).
struct Chunk {
    first: u32,
    stream: Vec<u16>,
    cnt: Vec<u16>,
    hits: Vec<(u32, u32)>,
}

/// Indexes the whole lines in data[lo..hi]; their first id is a multiple of 64,
/// so the chunk owns whole words of the shared bitmap rows.
fn scan_chunk(data: &[u8], lo: usize, hi: usize, plan: &Plan, blk: &Block) -> Chunk {
    let (rows, base) = (&blk.rows, blk.base);
    let first = id_at(data, lo);
    let (nl, words) = (plan.nlist, rows.len() / plan.nbm.max(1));
    // The list-term ids of each document, each document ended by u16::MAX.
    let mut stream = Vec::with_capacity((hi - lo) / 16);
    let (mut hits, mut doc, mut new, mut anch) = (Vec::new(), first, Vec::new(), Vec::new());
    // The bitmap words of the current 64 documents, stored when they are done.
    let mut group = vec![0u64; plan.nbm];
    let flush = |group: &mut [u64], doc: u32| {
        for (b, x) in group.iter_mut().enumerate() {
            rows[b * words + (doc - base) as usize / 64].store(std::mem::take(x), Relaxed);
        }
    };
    for_each_doc(data, lo, hi, plan, |tokens| {
        if doc % 64 == 0 && doc != first {
            flush(&mut group, doc - 1);
        }
        // Branch-free: write every term, keep the list terms and note the anchors.
        new.resize(tokens.len(), 0);
        anch.resize(tokens.len(), 0);
        let (mut n, mut m) = (0, 0);
        let bit = 1u64 << (doc & 63);
        for (p, &t) in tokens.iter().enumerate() {
            (new[n], anch[m]) = (t as u16, p);
            n += ((t as usize) < nl) as usize;
            m += (plan.role[t as usize] & ANCHOR != 0) as usize;
            if let Some(g) = group.get_mut((t as usize).wrapping_sub(nl)) {
                *g |= bit;
            }
        }
        stream.extend_from_slice(&new[..n]);
        stream.push(u16::MAX);
        // Phrases: compare the tokens around each anchor with its phrases,
        // after prefetching what that reads, a level for all anchors at a time.
        let ranges = |&p: &usize| plan.aoff[tokens[p] as usize] as usize..plan.aoff[tokens[p] as usize + 1] as usize;
        anch[..m].iter().for_each(|&p| prefetch(&plan.aoff[tokens[p] as usize]));
        anch[..m].iter().for_each(|p| _ = plan.anchors.get(ranges(p).start).map(prefetch));
        anch[..m].iter().flat_map(ranges).for_each(|a| prefetch(&plan.flat[plan.anchors[a].1 as usize]));
        for &p in &anch[..m] {
            let t = tokens[p] as usize;
            for &(q, s, n, j) in &plan.anchors[plan.aoff[t] as usize..plan.aoff[t + 1] as usize] {
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
    // Drop a term's repeats within a document (stamp[l] is the last document
    // of list l) and count the documents of each list.
    let (mut stamp, mut cnt, mut d, mut w) = (vec![u16::MAX; nl], vec![0u16; nl], 0u16, 0);
    for r in 0..stream.len() {
        let l = stream[r] as usize;
        if l == u16::MAX as usize {
            d = d.wrapping_add(1);
        } else if stamp[l] != d {
            (stamp[l], cnt[l]) = (d, cnt[l] + 1);
        } else {
            continue;
        }
        (stream[w], w) = (l as u16, w + 1);
    }
    Chunk { first: first.wrapping_sub(base), stream: stream[..w].to_vec(), cnt, hits }
}

/// Appends a query's answer line: the count, the id sum and the first ten ids.
fn line(out: &mut String, n: usize, sum: u64, top: impl Iterator<Item = u32>) {
    write!(out, "{n} {sum}").unwrap();
    top.take(10).for_each(|d| write!(out, " {d}").unwrap());
    out.push('\n');
}

/// Answers a BOOL query strictly left to right. The running result is a sorted
/// list `r` until a large set is ORed in, then the bitmap `bm`, which is all
/// zero whenever it is not in use.
fn boolean(q: &[(u8, u32)], plan: &Plan, blk: &Block, s: &mut Scratch, acc: &mut Sum) {
    let (rows, post, base) = (blk.rows(), |t| blk.post(t), blk.base);
    let words = s.bm.len();
    let (mut is_bm, r, bm, tl) = (false, &mut s.list, &mut s.bm, &mut s.tmp);
    r.clear();
    let get = |b: &[u64], d: u32| b[d as usize / 64] >> (d & 63) & 1 != 0;
    let set = |b: &mut [u64], d: u32| b[d as usize / 64] |= 1 << (d & 63);
    for &(op, t) in q {
        let t = t as usize;
        if plan.role[t] & BITMAP != 0 {
            let row = &rows[(t - plan.nlist) * words..][..words];
            match (is_bm, op) {
                (false, b'A') => r.retain(|&d| get(row, d)),
                (false, b'N') => r.retain(|&d| !get(row, d)),
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
        let df = post(t).len();
        let and = op == b'A';
        if !is_bm && (and || op == b'N') && r.len() * 16 < df {
            // Look the few ids of r up in the term's lists.
            let has = |d: u32| post(t).binary_search(&(d as u16)).is_ok();
            r.retain(|&d| has(d) == and);
            continue;
        }
        tl.clear();
        tl.extend(post(t).iter().map(|&d| d as u32));
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
            (true, b'N') => tl.iter().for_each(|&d| bm[d as usize / 64] &= !(1 << (d & 63))),
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
        return add(acc, base, r.len(), r.iter().map(|&d| d as u64).sum(), r.iter().copied());
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
    let ids = ids.flat_map(|(i, &x)| (0..64).filter(move |b| x >> b & 1 != 0).map(move |b| (i * 64 + b) as u32));
    add(acc, base, n, sum, ids);
    bm.fill(0);
}

/// A BOOL query's answer so far: the count, the id sum and the first ids.
type Sum = (usize, u64, [u32; 10]);

/// Adds a query's answer within the block from `base` on, after the blocks before.
fn add(acc: &mut Sum, base: u32, n: usize, sum: u64, ids: impl Iterator<Item = u32>) {
    (acc.0..10).zip(ids).for_each(|(i, d)| acc.2[i] = d + base);
    (acc.0, acc.1) = (acc.0 + n, acc.1 + sum + base as u64 * n as u64);
}

/// The block being indexed and queried: its first id, its bitmap rows of
/// `words` words each, and its lists, list l being docs[offs[l]..offs[l + 1]].
/// Threads fill the rows and lists in place, so they are atomics.
#[derive(Default)]
struct Block {
    base: u32,
    rows: Vec<AtomicU64>,
    offs: Vec<u32>,
    docs: Vec<AtomicU16>,
    cuts: Vec<usize>,
}

/// n zeros of type T viewed as its atomic A: zeroed pages straight from the OS.
fn zeros<T: Clone + Default, A>(n: usize) -> Vec<A> {
    let mut v = std::mem::ManuallyDrop::new(vec![T::default(); n]);
    // SAFETY: used for u64 and u16 with their atomics, of the same layout.
    unsafe { Vec::from_raw_parts(v.as_mut_ptr().cast(), n, v.capacity()) }
}

impl Block {
    /// The bitmap rows, once filled.
    fn rows(&self) -> &[u64] {
        // SAFETY: AtomicU64 has the layout of u64, and nothing writes them now.
        unsafe { std::slice::from_raw_parts(self.rows.as_ptr().cast(), self.rows.len()) }
    }

    /// List l, once filled.
    fn post(&self, l: usize) -> &[u16] {
        // SAFETY: as for rows.
        let docs: &[u16] = unsafe { std::slice::from_raw_parts(self.docs.as_ptr().cast(), self.docs.len()) };
        &docs[self.offs[l] as usize..self.offs[l + 1] as usize]
    }
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
    fn mallopt(param: i32, value: i32) -> i32;
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

    // One malloc arena, and big blocks mapped and unmapped: memory freed
    // after a block goes back to the OS. M_ARENA_MAX = -8, M_MMAP_THRESHOLD = -3.
    unsafe { (mallopt(-8, 1), mallopt(-3, 1 << 18)) };
    let qtext = fs::read(format!("{data_dir}/queries.txt")).expect("read queries.txt");
    let mut plan = Plan::default();
    plan.grow(1 << 12);
    let mut queries = Vec::new();
    for line in qtext.split(|&b| b == b'\n').filter(|l| !l.is_empty()) {
        let mut w = line.split(|&b| b == b' ');
        queries.push(if line.starts_with(b"BOOL") {
            // (operator, term) pairs; the leading "BOOL" acts as OR on the empty set.
            let mut pair = || Some((w.next()?[0], plan.intern(w.next()?, IN_BOOL)));
            Query::Bool(std::iter::from_fn(&mut pair).collect())
        } else {
            let terms = line[b"PHRASE \"".len()..line.len() - 1].split(|&b| b == b' ');
            Query::Phrase(terms.map(|w| plan.intern(w, 0)).collect())
        });
    }
    drop(qtext);
    let data = map_file(&format!("{data_dir}/docs.txt"));

    // Anchor each phrase on its rarest term in a sample of the corpus.
    // The id of every token no query uses: a term with no role.
    let none = plan.role.len() as u32;
    plan.keys.iter_mut().filter(|e| e[0] == 0).for_each(|e| e[2] = none as u64);
    plan.role.push(0);
    let (mut freq, mut sdocs, mut last) = (vec![0u32; plan.role.len()], 0, vec![u32::MAX; plan.role.len()]);
    for_each_doc(data, 0, line_start(data, SAMPLE), &plan, |tokens| {
        sdocs += 1;
        tokens.iter().for_each(|&t| { if last[t as usize] != sdocs { last[t as usize] = sdocs; freq[t as usize] += 1; } });
    });
    // A BOOL term in more than 1 of 32 sample documents gets a bitmap,
    // and so do the most frequent others beyond 65,535.
    let mut bools: Vec<usize> = (0..plan.role.len()).filter(|&t| plan.role[t] & IN_BOOL != 0).collect();
    bools.sort_by_key(|&t| std::cmp::Reverse(freq[t]));
    let common = bools.iter().filter(|&&t| freq[t] as usize * 32 > sdocs as usize).count();
    let nbm = common.max(bools.len().saturating_sub(65535));
    bools[..nbm].iter().for_each(|&t| plan.role[t] ^= IN_BOOL | BITMAP);
    (plan.nlist, plan.nbm) = (bools.len() - nbm, nbm);
    // Renumber the terms: list terms first, then bitmap terms, then the rest.
    let rest = (0..plan.role.len()).filter(|&t| plan.role[t] & (IN_BOOL | BITMAP) == 0);
    let order: Vec<usize> = bools[nbm..].iter().chain(&bools[..nbm]).copied().chain(rest).collect();
    let mut new = vec![0; order.len()];
    order.iter().enumerate().for_each(|(i, &t)| new[t] = i as u32);
    plan.keys.iter_mut().for_each(|e| e[2] = new[e[2] as usize] as u64);
    plan.long.values_mut().for_each(|t| *t = new[*t as usize]);
    plan.role = order.iter().map(|&t| plan.role[t]).collect();
    let freq: Vec<u32> = order.iter().map(|&t| freq[t]).collect();
    remap(&mut queries, &new);
    drop((last, order, new, bools));
    plan.queries = &queries;
    let mut list = Vec::new();
    for (qi, q) in queries.iter().enumerate() {
        if let Query::Phrase(p) = q {
            let j = (0..p.len()).min_by_key(|&j| freq[p[j] as usize]).unwrap();
            plan.role[p[j] as usize] |= ANCHOR;
            list.push((p[j], qi, &p[..], j));
        }
    }
    // One flat list of anchors, grouped by term, with copies of the phrases.
    list.sort_unstable_by_key(|a| a.0);
    plan.aoff = vec![0; plan.role.len() + 1];
    list.iter().for_each(|a| plan.aoff[a.0 as usize + 1] += 1);
    (1..plan.aoff.len()).for_each(|t| plan.aoff[t] += plan.aoff[t - 1]);
    for (_, qi, p, j) in list {
        plan.anchors
            .push((qi as u32, plan.flat.len() as u32, p.len() as u32, j as u32));
        plan.flat.extend_from_slice(p);
    }

    // Each BOOL query's cover, terms one of which every match contains: its
    // first term, joined by the term of each OR and replaced by the term of
    // an AND when that is rarer in the sample.
    let (mut cover, mut coff) = (Vec::new(), vec![0u32]);
    for q in &queries {
        if let Query::Bool(v) = q {
            let (mut c, mut f) = (Vec::new(), 0);
            for &(op, t) in v {
                match op {
                    b'A' if freq[t as usize] < f => (c, f) = (vec![t], freq[t as usize]),
                    b'A' | b'N' => {}
                    _ => (c.push(t), f += freq[t as usize]).1,
                }
            }
            cover.extend(c);
        }
        coff.push(cover.len() as u32);
    }

    // Blocks of equal bytes, at most 65,536 lines, cut where an id is a
    // multiple of 64, are indexed and queried one after the other. Each is
    // cut into chunks claimed by the threads in turn.
    let last = data[..data.len().saturating_sub(1)].iter().rposition(|&b| b == b'\n').map_or(0, |p| p + 1);
    let ndocs = if data.is_empty() { 0 } else { id_at(data, last) as usize + 1 };
    let id = |i: usize| id_at(data, i) as usize; // u32::MAX at the end
    // The first line at or after byte i whose id is a multiple of 64.
    let align = |mut i| {
        while i < data.len() && id(line_start(data, i)) % 64 != 0 {
            i = line_start(data, i) + 1;
        }
        line_start(data, i)
    };
    // The start of line t, at or after byte a: steps doubling ahead, then
    // bisection, so it reads only pages the scan has not yet passed.
    let below = |m: usize, t: usize| id(line_start(data, m)) < t;
    let pos = |t: usize, mut a: usize| {
        let mut b = a + 1;
        while b < data.len() && below(b, t) {
            (a, b) = (b, 3 * b - 2 * a);
        }
        let mut b = b.min(data.len());
        while a < b {
            let m = (a + b) / 2;
            (a, b) = if below(m, t) { (m + 1, b) } else { (a, m) };
        }
        line_start(data, a)
    };
    // Blocks of equal numbers of lines, at most 32,768 and a multiple of 64.
    let bdocs = ndocs.div_ceil(ndocs.div_ceil(1 << 15).max(1)).next_multiple_of(64).max(64);
    let nsub = 2 * nthreads;
    let sums: Vec<Mutex<Sum>> = (0..queries.len()).map(|_| Default::default()).collect();
    let (hits, blk, chunks) = (Mutex::new(Vec::new()), RwLock::new(Block::default()), Mutex::new(Vec::new()));
    let next = AtomicUsize::new(0);
    let claim = |n| (0..).map(|_| next.fetch_add(1, Relaxed)).take_while(move |&k| k < n);
    let (qblock, nl) = (64, plan.nlist);
    // A barrier that spins (yielding): the last thread to arrive runs f first.
    let (count, round) = (AtomicUsize::new(0), AtomicUsize::new(0));
    let wait = |f: &dyn Fn()| {
        let r = round.load(SeqCst);
        if count.fetch_add(1, SeqCst) + 1 == nthreads {
            (f(), count.store(0, SeqCst), round.fetch_add(1, SeqCst));
        } else {
            while round.load(SeqCst) == r {
                thread::yield_now();
            }
        }
    };
    // The threads go through the blocks together, waiting for each other
    // between the steps.
    par(nthreads, |_| {
        let mut s = Scratch::default();
        for base in (0..ndocs).step_by(bdocs) {
            let n = bdocs.min(ndocs - base);
            let words = n.div_ceil(64);
            wait(&|| {
                let mut b = blk.write().unwrap();
                let lo = b.cuts.last().copied().unwrap_or(0);
                let hi = pos(base + n, lo);
                // Chunks of about equal bytes.
                let cuts = (0..=nsub).map(|k| align(lo + k * (hi - lo) / nsub).min(hi));
                *b = Block { base: base as u32, rows: zeros::<u64, _>(plan.nbm * words), cuts: cuts.collect(), ..Default::default() };
                *chunks.lock().unwrap() = (0..nsub).map(|_| None).collect();
                next.store(0, Relaxed);
            });
            {
                let b = blk.read().unwrap();
                for k in claim(nsub) {
                    let c = scan_chunk(data, b.cuts[k], b.cuts[k + 1], &plan, &b);
                    chunks.lock().unwrap()[k] = Some(c);
                }
            }
            // The block's lists: a chunk's ids of list l go cnt[l] places
            // after its start, cnt[l] counting the ids of l in the chunks before it.
            wait(&|| {
                let (mut b, mut offs) = (blk.write().unwrap(), vec![0u32; nl + 1]);
                for c in chunks.lock().unwrap().iter_mut().flatten() {
                    c.cnt.iter_mut().zip(&mut offs[1..]).for_each(|(x, o)| (*x, *o) = (*o as u16, *o + *x as u32));
                }
                (1..=nl).for_each(|t| offs[t] += offs[t - 1]);
                (b.docs, b.offs) = (zeros::<u16, _>(offs[nl] as usize), offs);
                next.store(0, Relaxed);
            });
            {
                let b = blk.read().unwrap();
                for k in claim(nsub) {
                    let mut c = chunks.lock().unwrap()[k].take().unwrap();
                    let mut d = c.first as u16;
                    for &l in &c.stream {
                        let l = l as usize;
                        if l == u16::MAX as usize {
                            d = d.wrapping_add(1);
                        } else {
                            b.docs[(b.offs[l] + c.cnt[l] as u32) as usize].store(d, Relaxed);
                            c.cnt[l] += 1;
                        }
                    }
                    hits.lock().unwrap().extend(c.hits);
                }
            }
            // Answer the BOOL queries that can match in this block.
            wait(&|| next.store(0, Relaxed));
            let b = blk.read().unwrap();
            s.bm.resize(words, 0);
            for qb in claim(queries.len().div_ceil(qblock)) {
                for qi in qb * qblock..((qb + 1) * qblock).min(queries.len()) {
                    // Only if a term of its cover occurs in the block.
                    let mut cover = cover[coff[qi] as usize..coff[qi + 1] as usize].iter().map(|&t| t as usize);
                    if let Query::Bool(q) = &queries[qi] {
                        if cover.any(|t| plan.role[t] & BITMAP != 0 || !b.post(t).is_empty()) {
                            boolean(q, &plan, &b, &mut s, &mut sums[qi].lock().unwrap());
                        }
                    }
                }
            }
        }
    });
    let mut hits = hits.into_inner().unwrap();
    // Phrase matches by query, each in ascending id order.
    hits.sort_unstable();
    let mut hoff = vec![0usize; queries.len() + 1];
    hits.iter().for_each(|h| hoff[h.0 as usize + 1] += 1);
    (1..hoff.len()).for_each(|i| hoff[i] += hoff[i - 1]);

    // Format blocks of answers, claimed by the threads in turn.
    next.store(0, Relaxed);
    let mut outs: Vec<(usize, String)> = par(nthreads, |_| {
        claim(queries.len().div_ceil(qblock))
            .map(|b| {
                let mut out = String::new();
                for qi in b * qblock..((b + 1) * qblock).min(queries.len()) {
                    match &queries[qi] {
                        Query::Bool(_) => {
                            let s = sums[qi].lock().unwrap();
                            line(&mut out, s.0, s.1, s.2[..s.0.min(10)].iter().copied());
                        }
                        Query::Phrase(_) => {
                            let mut d: Vec<u32> = hits[hoff[qi]..hoff[qi + 1]].iter().map(|h| h.1).collect();
                            d.dedup(); // a phrase can occur twice in a document
                            line(&mut out, d.len(), d.iter().map(|&x| x as u64).sum(), d.into_iter());
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
