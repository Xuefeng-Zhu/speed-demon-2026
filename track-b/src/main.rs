//! Speed Demon 2026, Track B (Index). Standard library only.
//!
//! 1. Parse the queries first and intern every term they use. A sample of the
//!    corpus picks the frequent BOOL terms, which get bitmaps, and the
//!    rarest term of each phrase, its anchor.
//! 2. Map docs.txt and split it into chunks of whole lines (at most 16 MiB)
//!    that threads claim in turn. Each chunk is tokenized once: it sets the bits of the frequent terms
//!    in global bitmaps, builds posting lists of chunk-local u16 ids for the
//!    other BOOL terms, and checks phrases around each anchor occurrence.
//! 3. Threads then answer blocks of queries on a bitmap of all documents.

use std::fmt::Write as _;
use std::sync::atomic::{AtomicU64, AtomicUsize, Ordering::Relaxed};
use std::{env, fs, thread};

/// Term id of a token that no query uses.
const MISS: u32 = u32::MAX;
/// Bytes of corpus read up front to estimate the document frequencies.
const SAMPLE: usize = 1 << 19;
/// Bytes of corpus a thread scans between releasing what it has read.
const SLICE: usize = 1 << 22;
/// Bytes in a segment of the stream of sparse terms.
const SEG: usize = 1 << 16;
/// Term roles: BOOL term with a posting list; anchors a phrase; frequent BOOL
/// term with a bitmap.
const SPARSE: u8 = 1;
const ANCHOR: u8 = 2;
const BITMAP: u8 = 4;

/// A token packed into 32 bytes, zero-padded; tokens never contain a zero byte.
#[derive(Clone, Copy, PartialEq, Eq)]
#[repr(align(32))]
struct Key([u64; 4]);

/// Packs the n-byte token at data[s..]. Token bytes are ASCII letters and
/// digits, so OR-ing 0x20 lowercases letters and leaves digits alone.
fn key(data: &[u8], s: usize, n: usize) -> Key {
    let mut pad = [0u8; 32];
    let src = data.get(s..s + 32).unwrap_or_else(|| {
        pad[..n].copy_from_slice(&data[s..s + n]);
        &pad
    });
    Key(std::array::from_fn(|w| {
        let x = u64::from_le_bytes(src[w * 8..w * 8 + 8].try_into().unwrap());
        let valid = n.saturating_sub(w * 8).min(8);
        (x | 0x2020_2020_2020_2020) & ((1u128 << (valid * 8)) - 1) as u64
    }))
}

/// The queries and their terms: an open-addressing table from token to dense
/// term id, and what the corpus scan does with each term: its roles, the
/// phrases it anchors, anchors[aoff[t]..aoff[t + 1]] for term t, as (query,
/// start of the phrase in `flat`, the terms of all queries, its length,
/// position of the term in it),
/// and brow[t]: the bitmap of a BITMAP term, or the number of a sparse one.
#[derive(Default)]
struct Plan {
    slots: Vec<u32>,
    keys: Vec<Key>,
    role: Vec<u8>,
    aoff: Vec<u32>,
    anchors: Vec<(u32, u32, u32, u32)>,
    flat: Vec<u32>,
    brow: Vec<u32>,
}

impl Plan {
    /// The home slot of `k`.
    fn hash(&self, k: &Key) -> usize {
        let [a, b, c, d] = k.0;
        let h = (a ^ b.rotate_left(17) ^ c.rotate_left(31) ^ d.rotate_left(47))
            .wrapping_mul(0x9e37_79b9_7f4a_7c15);
        (h >> 32) as usize & (self.slots.len() - 1)
    }

    /// The slot of `k`, probing from its home slot `h`, and the id in it.
    fn slot(&self, k: &Key, h: usize) -> (usize, u32) {
        let mask = self.slots.len() - 1;
        let done = |&i: &usize| self.slots[i] == MISS || self.keys[self.slots[i] as usize] == *k;
        let i = (h..).map(|i| i & mask).find(done).unwrap();
        (i, self.slots[i])
    }

    /// The id of the term `k`, added if new, after adding `role` to its roles.
    fn intern(&mut self, k: Key, role: u8) -> u32 {
        let (i, id) = self.slot(&k, self.hash(&k));
        if id == MISS {
            self.slots[i] = self.keys.len() as u32;
            self.keys.push(k);
            self.role.push(0);
        }
        self.role[self.slots[i] as usize] |= role;
        self.slots[i]
    }
}

/// Calls `f` with the term ids (plan.keys.len() for a token no query uses) of
/// each document in data[lo..hi], which must be whole lines. Pages are released
/// as the scan passes them, so only a few of them stay resident.
fn for_each_doc(data: &[u8], lo: usize, hi: usize, plan: &Plan, mut f: impl FnMut(&[u32])) {
    let (mut i, mut done, mut tokens, mut keys) = (lo, lo, Vec::new(), Vec::new());
    let (mut starts, mut ends) = (Vec::new(), Vec::new());
    while i < hi {
        i += data[i..].iter().position(|&b| b == b'\t').unwrap() + 1;
        // Where the tokens of the document start and end, from masks of 64
        // bytes at a time up to its LF. Bit p of `after`: byte p - 1 is in a token.
        let mut carry = 0;
        loop {
            let (m, lf) = masks(data, i);
            let m = m & (lf & lf.wrapping_neg()).wrapping_sub(1);
            let after = m << 1 | carry;
            push_bits(m & !after, i, &mut starts);
            push_bits(!m & after, i, &mut ends);
            carry = m >> 63;
            i += (lf.trailing_zeros() as usize + 1).min(64);
            if lf != 0 {
                break;
            }
        }
        // Key every token of the document and prefetch its slot, then look
        // them all up, so that many cache misses are in flight at once.
        for (&s, &e) in starts.iter().zip(&ends) {
            // A longer token is no term; all-ones bytes never match one.
            let k = (e - s <= 32)
                .then(|| key(data, s, e - s))
                .unwrap_or(Key([!0; 4]));
            let h = plan.hash(&k);
            prefetch(&plan.slots[h]);
            keys.push((k, h));
        }
        starts.clear();
        ends.clear();
        keys.iter()
            .for_each(|(_, h)| _ = plan.keys.get(plan.slots[*h] as usize).map(prefetch));
        let none = plan.keys.len() as u32;
        tokens.extend(keys.iter().map(|(k, h)| plan.slot(k, *h).1.min(none)));
        f(&tokens);
        tokens.clear();
        keys.clear();
        if i - done >= SLICE || i >= hi {
            release(&data[done..i]);
            done = i;
        }
    }
}

/// Calls f(s, d) for each sparse number s of document d in a segment of the
/// stream; `d` counts the documents.
fn decode(seg: &[u8], d: &mut u16, mut f: impl FnMut(usize, u16)) {
    let mut i = 0;
    while i < seg.len() {
        let (mut v, mut shift) = (0, 0);
        loop {
            v |= (seg[i] as usize & 127) << shift;
            shift += 7;
            i += 1;
            if seg[i - 1] < 128 {
                break;
            }
        }
        match v {
            0 => *d += 1,
            _ => f(v - 1, *d),
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
    let (mut m, mut lf) = (0u64, 0u64);
    for j in 0..64 {
        let c = b[j];
        let tok = (c | 0x20).wrapping_sub(b'a') < 26 || c.wrapping_sub(b'0') < 10;
        m |= (tok as u64) << j;
        lf |= ((c == b'\n') as u64) << j;
    }
    (m, lf)
}

/// Pushes base + p for each set bit p of x, in ascending order.
fn push_bits(mut x: u64, base: usize, v: &mut Vec<usize>) {
    while x != 0 {
        v.push(base + x.trailing_zeros() as usize);
        x &= x - 1;
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

/// Applies a BOOL operator to one bit of each document.
fn apply(op: u8, x: u64, y: u64) -> u64 {
    match op {
        b'A' => x & y,
        b'N' => x & !y,
        _ => x | y,
    }
}

/// The decimal number at data[i..], up to the first non-digit.
fn number(data: &[u8], i: usize) -> u32 {
    let digits = data[i.min(data.len())..].iter().take_while(|b| b.is_ascii_digit());
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
    if len == 0 {
        return &[];
    }
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
    // Each term follows a space, so the table stays at most half full.
    let mut plan = Plan {
        slots: vec![MISS; (2 * qtext.iter().filter(|&&b| b == b' ').count()).next_power_of_two()],
        ..Default::default()
    };
    // Query q has the terms flat[qoff[q]..qoff[q + 1]], each after the
    // operator ops[k]: the first byte of AND, NOT or OR, b'B' for the first
    // term of a BOOL query ("BOOL" acts as OR on the empty set), b'P' in a
    // phrase. Terms are first noted by position, then interned in one loop
    // that prefetches the slots of the terms ahead.
    let (mut ops, mut occ, mut qoff, mut i) = (Vec::new(), Vec::new(), vec![0], 0);
    while i < qtext.len() {
        let mut op = qtext[i];
        i += if op == b'P' { 8 } else { 5 };
        loop {
            let n = qtext[i..].iter().position(|b| !b.is_ascii_alphanumeric()).unwrap();
            (occ.push((i, n)), ops.push(op));
            i += n + 1 + (qtext[i + n] == b'"') as usize;
            if qtext[i - 1] == b'\n' {
                break;
            }
            if op != b'P' {
                op = qtext[i];
                i += if op == b'O' { 3 } else { 4 };
            }
        }
        qoff.push(ops.len());
    }
    for (k, &(s, n)) in occ.iter().enumerate() {
        _ = occ
            .get(k + 16)
            .map(|&(s, n)| prefetch(&plan.slots[plan.hash(&key(&qtext, s, n))]));
        let id = plan.intern(key(&qtext, s, n), (ops[k] != b'P') as u8 * SPARSE);
        plan.flat.push(id);
    }
    drop((occ, qtext));
    let data = map_file(&format!("{data_dir}/docs.txt"));
    let nq = qoff.len() - 1;

    // Document frequencies estimated from a sample of the corpus.
    // The id of every token no query uses: a term with no role.
    plan.role.push(0);
    let nterms = plan.role.len();
    let (mut freq, mut sdocs) = (vec![0u32; nterms], 0);
    for_each_doc(data, 0, line_start(data, SAMPLE), &plan, |tokens| {
        sdocs += 1;
        tokens.iter().for_each(|&t| freq[t as usize] += 1);
    });
    // A BOOL term seen more than once per 32 sample documents gets a bitmap,
    // bitmap brow[t]; the others are numbered for their posting lists.
    let (mut nbits, mut nsparse) = (0, 0);
    plan.brow = (0..nterms)
        .map(|t| match plan.role[t] & SPARSE != 0 {
            true if freq[t] as usize * 32 > sdocs => {
                plan.role[t] ^= SPARSE | BITMAP;
                nbits += 1;
                nbits - 1
            }
            true => {
                nsparse += 1;
                MISS
            }
            false => MISS,
        })
        .collect();
    // Sparse terms are numbered by falling sample frequency, so that the most
    // common ones take the fewest bytes in the stream below.
    let mut sp: Vec<_> = (0..nterms).filter(|&t| plan.role[t] & SPARSE != 0).collect();
    sp.sort_by_key(|&t| std::cmp::Reverse(freq[t]));
    sp.iter().enumerate().for_each(|(i, &t)| plan.brow[t] = i as u32);
    let (nbits, ns) = (nbits as usize, nsparse as usize);
    // Anchor each phrase on its rarest term in the sample.
    let mut list = Vec::new();
    for qi in (0..nq).filter(|&q| ops[qoff[q]] == b'P') {
        let p = &plan.flat[qoff[qi]..qoff[qi + 1]];
        let j = (0..p.len()).min_by_key(|&j| freq[p[j] as usize]).unwrap();
        list.push((p[j], qi, qoff[qi], p.len(), j));
    }
    // One flat list of anchors, grouped by term, with copies of the phrases.
    list.sort_unstable_by_key(|a| a.0);
    plan.aoff = vec![0; nterms + 1];
    list.iter().for_each(|a| plan.aoff[a.0 as usize + 1] += 1);
    (1..=nterms).for_each(|t| plan.aoff[t] += plan.aoff[t - 1]);
    for (t, qi, s, n, j) in list {
        plan.role[t as usize] |= ANCHOR;
        plan.anchors.push((qi as u32, s as u32, n as u32, j as u32));
    }

    // The id of the last line gives the number of documents.
    let tail = &data[..data.len().saturating_sub(1)];
    let last = tail.iter().rposition(|&b| b == b'\n').map_or(0, |j| j + 1);
    let ndocs = if data.is_empty() { 0 } else { number(data, last) as usize + 1 };
    let words = ndocs.div_ceil(64);
    let mut store = vec![0u64; nbits * words];
    // Threads OR whole words into the bitmaps; bitmap i is bits[i * words..][..words].
    let bits = unsafe { &*(store.as_mut_slice() as *mut [u64] as *const [AtomicU64]) };
    // Chunks of at most 16 MiB, so that ids local to a chunk fit in 16 bits
    // (documents average about 1 KB); threads claim them in turn.
    let nchunks = nthreads.max((data.len() >> 24) + 1);
    let (cut, next) = (|k| line_start(data, k * data.len() / nchunks), AtomicUsize::new(0));
    let plan = &plan;
    // Each chunk: its first id, its posting lists (sparse term s owns
    // docs[offs[s]..offs[s + 1]], ids local to the chunk) and phrase matches.
    let chunk = |k| {
        let (lo, hi) = (cut(k), cut(k + 1));
        let first = number(data, lo);
        let (mut doc, mut block, mut hits) = (first, vec![0u64; nbits + 1], Vec::new());
        let (mut stream, mut seg) = (Vec::new(), Vec::with_capacity(SEG));
        let (mut new, mut anch) = (Vec::new(), Vec::new());
        // ORs the bits of the 64 documents of group g into the bitmaps.
        let flush = |block: &mut [u64], g: usize| {
            for (i, w) in block[..nbits].iter_mut().enumerate().filter(|(_, w)| **w != 0) {
                bits[i * words + g].fetch_or(std::mem::take(w), Relaxed);
            }
        };
        let mut group = first as usize >> 6;
        for_each_doc(data, lo, hi, plan, |tokens| {
            if doc as usize >> 6 != group {
                flush(&mut block, group);
                group = doc as usize >> 6;
            }
            // Branch-free: write every term, keep the sparse ones, and note
            // where the anchors are. The stream holds sparse number + 1 as a
            // varint, and ends each document with a zero byte.
            new.resize(3 * tokens.len() + 4, 0);
            anch.resize(tokens.len(), 0);
            let (mut n, mut m) = (0, 0);
            for (p, &t) in tokens.iter().enumerate() {
                let role = plan.role[t as usize];
                let v = plan.brow[t as usize].wrapping_add(1);
                let (a, b) = ((v >= 1 << 7) as u32, (v >= 1 << 14) as u32);
                let x = v & 127 | a << 7 | (v >> 7 & 127 | b << 7) << 8 | (v >> 14) << 16;
                new[n..n + 4].copy_from_slice(&x.to_le_bytes());
                anch[m] = p;
                n += (1 + a + b) as usize * (role & SPARSE != 0) as usize;
                m += (role & ANCHOR != 0) as usize;
                let i = if role & BITMAP != 0 { plan.brow[t as usize] as usize } else { nbits };
                block[i] |= 1 << (doc & 63);
            }
            new[n] = 0;
            if seg.len() + n >= SEG {
                stream.push(std::mem::replace(&mut seg, Vec::with_capacity(SEG)));
            }
            seg.extend_from_slice(&new[..=n]);
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
        flush(&mut block, group);
        stream.push(seg);
        // Counting sort of the stream into CSR, freeing it as it goes.
        // A term repeated in a document is listed once: last[s] is the last
        // document listed for s. offs[s] serves as the write position of s.
        let (mut offs, mut last) = (vec![0u32; ns + 1], vec![MISS; ns]);
        let mut add = |s: usize, d: u16| std::mem::replace(&mut last[s], d as u32) != d as u32;
        let mut d = 0;
        stream.iter().for_each(|seg| {
            decode(seg, &mut d, |s, d| offs[s + 1] += add(s, d) as u32);
        });
        (1..=ns).for_each(|s| offs[s] += offs[s - 1]);
        let (mut docs, mut d) = (vec![0u16; offs[ns] as usize], 0);
        last.fill(MISS);
        let mut add = |s: usize, d: u16| std::mem::replace(&mut last[s], d as u32) != d as u32;
        for seg in stream {
            decode(&seg, &mut d, |s, d| {
                if add(s, d) {
                    docs[offs[s] as usize] = d;
                    offs[s] += 1;
                }
            });
        }
        (1..=ns).rev().for_each(|s| offs[s] = offs[s - 1]);
        offs[0] = 0;
        (first, offs, docs, hits)
    };
    let claim = || std::iter::from_fn(|| Some(next.fetch_add(1, Relaxed)).filter(|&k| k < nchunks));
    let mut chunks: Vec<_> = par(nthreads, |_| claim().map(|k| (k, chunk(k))).collect::<Vec<_>>())
        .into_iter()
        .flatten()
        .collect();
    chunks.sort_unstable_by_key(|c| c.0);
    let chunks: Vec<_> = chunks.into_iter().map(|c| c.1).collect();
    // Phrase matches by query, in document order: pdocs[poff[q]..poff[q + 1]].
    let mut poff = vec![0u32; nq + 1];
    chunks.iter().flat_map(|c| &c.3).for_each(|&(q, _)| poff[q as usize + 1] += 1);
    (1..=nq).for_each(|q| poff[q] += poff[q - 1]);
    let (mut cur, mut pdocs) = (poff.clone(), vec![0u32; poff[nq] as usize]);
    for &(q, d) in chunks.iter().flat_map(|c| &c.3) {
        pdocs[cur[q as usize] as usize] = d;
        cur[q as usize] += 1;
    }

    // BOOL queries: strictly left-to-right set algebra on the bitmap `r`.
    let format = |qs: std::ops::Range<usize>| {
        let (mut out, mut r, mut tmp) = (String::new(), vec![0u64; words], vec![0u64; words]);
        for qi in qs {
            let (mut n, mut sum, mut top) = (0u64, 0u64, Vec::new());
            let (a, b) = (qoff[qi], qoff[qi + 1]);
            if ops[a] != b'P' {
                for (&op, &t) in ops[a..b].iter().zip(&plan.flat[a..b]) {
                    let (b, sparse) = (plan.brow[t as usize] as usize, plan.role[t as usize] & SPARSE != 0);
                    if !sparse {
                        let b = &store[b * words..][..words];
                        r.iter_mut().zip(b).for_each(|(x, &y)| *x = apply(op, *x, y));
                        continue;
                    }
                    let posts = chunks.iter().flat_map(|(first, offs, docs, _)| {
                        docs[offs[b] as usize..offs[b + 1] as usize].iter().map(move |&d| *first as usize + d as usize)
                    });
                    let bit = |d: usize| (d >> 6, 1u64 << (d & 63));
                    if op == b'A' {
                        tmp.fill(0);
                        posts.map(bit).for_each(|(w, m)| tmp[w] |= r[w] & m);
                        std::mem::swap(&mut r, &mut tmp);
                    } else {
                        posts.map(bit).for_each(|(w, m)| r[w] = apply(op, r[w], m));
                    }
                }
                // Eight zero words skipped at a time; clears `r` for the next
                // query. The positions of the set bits of x sum to the sum
                // over k of 2^k times the count of those with bit k.
                for (i, c) in r.chunks_mut(8).enumerate() {
                    if c.iter().fold(0, |a, x| a | x) == 0 {
                        continue;
                    }
                    for (j, x) in c.iter_mut().enumerate() {
                        let x = std::mem::take(x);
                        let id = ((i * 8 + j) * 64) as u64;
                        let mut y = x;
                        while y != 0 && top.len() < 10 {
                            top.push(id as u32 + y.trailing_zeros());
                            y &= y - 1;
                        }
                        let pos = (0..6)
                            .map(|k| ((x & !(!0 / ((1 << (1 << k)) + 1))).count_ones() as u64) << k);
                        n += x.count_ones() as u64;
                        sum += id * x.count_ones() as u64 + pos.sum::<u64>();
                    }
                }
            } else {
                let mut ids = pdocs[poff[qi] as usize..poff[qi + 1] as usize].to_vec();
                ids.dedup(); // a phrase can occur twice in a document
                n = ids.len() as u64;
                sum = ids.iter().map(|&d| d as u64).sum();
                top.extend(ids.iter().take(10));
            }
            write!(out, "{n} {sum}").unwrap();
            top.iter().for_each(|d| write!(out, " {d}").unwrap());
            out.push('\n');
        }
        out
    };
    let block = nq.div_ceil(nthreads);
    let outs = par(nthreads, |k| format(k * block..((k + 1) * block).min(nq)));
    fs::create_dir_all(&out_dir).ok();
    fs::write(format!("{out_dir}/results.txt"), outs.concat()).expect("write results.txt");
}
