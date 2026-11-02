//! Speed Demon 2026, Track B (Index). Standard library only.
//!
//! 1. Parse the queries and intern every term they use, on all threads. From
//!    a small sample of the corpus: frequent BOOL terms get bitmaps, the others posting
//!    lists; each phrase is anchored on its rarest term, and each BOOL query
//!    gets trigger terms whose sets hold its result.
//! 2. Map docs.txt and cut it into chunks of whole lines, each starting at a
//!    multiple of 64 documents, claimed by the threads in turn while one more
//!    thread sets up the answers. A thread tokenizes its chunk once: it sets
//!    the bitmap bits of the chunk's documents, builds u16 posting lists local
//!    to the chunk, and checks the phrases around each anchor occurrence.
//! 3. The thread then answers, on that chunk alone, every BOOL query whose
//!    trigger terms occur in it (strictly left to right, on a sorted list
//!    that switches to a bitmap when a large set is ORed in), adds each
//!    answer to the query's count, id sum and ten smallest ids, and reuses
//!    the chunk's buffers for its next one, so only the chunks in progress
//!    are in memory.

use std::sync::atomic::{AtomicU32, AtomicU64, AtomicU8, AtomicUsize, Ordering::*};
use std::sync::Mutex;
use std::{collections::HashMap, fmt::Write as _, fs, io::Write as _, os::fd::AsRawFd, thread};


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
/// (BOOL terms) are 0..nlist, nlist <= 65,535, so their ids fit a u16; the
/// BITMAP terms follow, term nlist + i with bitmap i of nbm. For the scan, the
/// table is rebuilt without collisions: bucket displacements `disp` (see `at`).
#[derive(Default)]
struct Plan {
    keys: &'static mut [[u64; 4]],
    disp: Vec<u16>,
    long: HashMap<Vec<u8>, u64>,
    phr: Vec<u32>,
    nlist: usize,
    nbm: usize,
    /// Query i is (b'B' or b'P', its first term in `terms`); a sentinel ends qs.
    qs: Vec<(u8, u32)>,
    terms: Vec<(u8, u32)>,
}

/// What answering needs beyond the plan: BOOL query i's result is within the
/// union of the sets of the terms trig[toff[i]..toff[i + 1]], so it is empty
/// in a chunk without them; and every query's answer so far: (trig, toff, acc).
type Late = (Vec<u32>, Vec<u32>, Vec<Acc>);

    /// The 24-bit hash of the key k; its low bits are the home slot.
    fn hash(k: [u64; 2]) -> usize {
        ((k[0] ^ k[1].rotate_left(29)).wrapping_mul(0x9e37_79b9_7f4a_7c15) >> 40) as usize
    }

    /// The 64-bit mix of the key k, distinct for distinct keys (in practice).
    fn mix(k: [u64; 2]) -> u64 {
        // Not k[0] ^ f(k[1]): xor folds two keys onto one too easily.
        let x = k[1].wrapping_mul(0xff51_afd7_ed55_8ccd).wrapping_add(k[0]);
        x.wrapping_mul(0x9e37_79b9_7f4a_7c15)
    }

    /// The slot of the key with mix x in the collision-free table: its bucket's
    /// displacement d picks the hash ((x ^ d) * odd) of x.
    fn at(x: u64, disp: &[u16], n: usize) -> usize {
        let d = disp[(x >> (64 - disp.len().trailing_zeros())) as usize];
        ((x ^ d as u64).wrapping_mul(0xd6e8_feb8_6659_fd93) >> (64 - n.trailing_zeros())) as usize
    }

    /// Moves every key to its own slot (hash and displace): buckets of about two
    /// keys, the largest first, each with the first d whose slots are all free.
    /// Returns the old table, which the caller unmaps.
    fn perfect(pl: &mut Plan) -> &'static mut [[u64; 4]] {
        let (n, nb) = (pl.keys.len(), (pl.keys.len() / 4).max(2));
        let b = |e: &[u64; 4]| (e[3] >> (64 - nb.trailing_zeros())) as usize;
        let mut off = vec![0u32; nb + 1];
        for e in pl.keys.iter_mut().filter(|e| e[0] != 0) {
            e[3] = mix([e[0], e[1]]); // kept in the spare word
            off[b(e) + 1] += 1;
        }
        let max = *off.iter().max().unwrap() as usize;
        (1..=nb).for_each(|i| off[i] += off[i - 1]);
        let (mut by, mut fill) = (vec![0u32; off[nb] as usize], off.clone());
        for (j, e) in pl.keys.iter().enumerate().filter(|e| e.1[0] != 0) {
            (by[fill[b(e)] as usize] = j as u32, fill[b(e)] += 1);
        }
        let old = std::mem::take(&mut pl.keys);
        resize(n, pl); // an empty table: old is unmapped after the moves
        let (slots, mut used) = (&mut Vec::new(), vec![0u64; n.div_ceil(64)]);
        pl.disp = vec![0; nb];
        for size in (1..=max).rev() {
            for i in (0..nb).filter(|&i| (off[i + 1] - off[i]) as usize == size) {
                let g = &by[off[i] as usize..off[i + 1] as usize];
                for d in 0..=u16::MAX {
                    pl.disp[i] = d;
                    slots.clear();
                    for &j in g {
                        let s = at(old[j as usize][3], &pl.disp, n);
                        if used[s / 64] >> (s % 64) & 1 != 0 || slots.contains(&s) {
                            break;
                        }
                        slots.push(s);
                    }
                    if slots.len() == size {
                        break;
                    }
                    assert!(d < u16::MAX, "no displacement");
                }
                for (&j, &s) in g.iter().zip(&*slots) {
                    (pl.keys[s], used[s / 64]) = (old[j as usize], used[s / 64] | 1 << (s % 64));
                }
            }
        }
        std::mem::forget((off, by, fill)); // freed, they would change how malloc grows
        old
    }

    /// Rebuilds the table with n zeroed 32-byte slots (none straddles two cache
    /// lines), on 2 MiB pages if the table is large, so that the scan's random
    /// lookups need few TLB entries.
    fn resize(n: usize, pl: &mut Plan) {
        // PROT_READ | PROT_WRITE; MAP_PRIVATE | MAP_ANONYMOUS (Linux).
        let p = unsafe { mmap(std::ptr::null_mut(), n * 32 + (2 << 20), 3, 0x22, -1, 0) };
        let a = (p as usize).next_multiple_of(2 << 20);
        unsafe { madvise(a as *mut u8, n * 32, 14) }; // MADV_HUGEPAGE on Linux
        let new = unsafe { std::slice::from_raw_parts_mut(a as *mut [u64; 4], n) };
        let old = std::mem::replace(&mut pl.keys, new);
        for &mut e in old.iter_mut().filter(|e| e[0] != 0) {
            pl.keys[slot(pl.keys, [e[0], e[1]])] = e;
        }
        unsafe { munmap(old.as_mut_ptr().cast(), old.len() * 32) };
    }

/// The slot of the key k in the probing table keys: k's, or the empty one it would take.
fn slot(keys: &[[u64; 4]], k: [u64; 2]) -> usize {
    let hit = |&i: &usize| keys[i][..2] == k || keys[i][0] == 0;
    let mask = keys.len() - 1;
    (hash(k)..).map(|i| i & mask).find(hit).unwrap()
}

/// Calls `f` with the term ids (term 0's for a token no query uses) of
/// each document in data, which must be whole lines. Pages are released
/// as the scan passes them, so only a few of them stay resident.
fn for_each_doc(data: &[u8], plan: &Plan, mut f: impl FnMut(&[u32], &[(usize, usize)])) {
    let (mut i, mut done, mut tokens, mut keys, mut anch) = (0, 0, vec![], vec![], vec![]);
    let (tbl, disp) = (&*plan.keys, &plan.disp[..]);
    let none = tbl.iter().find(|e| e[0] == 0).unwrap()[2]; // term 0, which empty slots hold
    let long = |w: &[u8]| *plan.long.get(&w.to_ascii_lowercase()).unwrap_or(&none);
    while i < data.len() {
        // Key every token but the id and prefetch its slot, then look them all
        // up, so that many cache misses are in flight at once. A short token
        // is a query term if and only if its one slot holds its key. A long
        // token is looked up by its bytes, at its start and length.
        i = each_token(data, i, true, |s, e| {
            let k = key(data, s, e - s);
            let h = at(mix(k), disp, tbl.len());
            prefetch(unsafe { &*tbl.as_ptr().add(h) }); // h < tbl.len()
            let w = ([s as u64, (e - s) as u64], usize::MAX);
            keys.push(if e - s > 16 { w } else { (k, h) });
        });
        tokens.extend(keys.iter().enumerate().map(|(j, &(k, h))| {
            let w = || long(&data[k[0] as usize..][..k[1] as usize]);
            let find = |i: usize| {
                let e = unsafe { tbl.get_unchecked(i) }; // i < tbl.len()
                std::hint::select_unpredictable((e[0] == k[0]) & (e[1] == k[1]), e[2], none)
            };
            let v = if h == usize::MAX { w() } else { find(h) };
            // An anchor: its phrases start at phr[(v >> 32) - 1].
            if v >> 32 != 0 {
                prefetch(&plan.phr[(v >> 32) as usize - 1]);
                anch.push((j, (v >> 32) as usize - 1));
            }
            v as u32
        }));
        f(&tokens, &anch);
        (tokens.clear(), keys.clear(), anch.clear());
        if i - done >= 1 << 20 || i >= data.len() {
            // 1 MiB scanned since the last release, or the end.
            release(&data[done..i.min(data.len())]);
            done = i;
        }
    }
}

/// Calls f(s, e) for each token data[s..e] of the line from byte i, but the first
/// if `id` (a document's id), and returns the start of the next line (or a
/// position past the end of data). The bounds come from masks of 64 bytes at a
/// time; bit p of `after`: byte p - 1 is in a token.
fn each_token(data: &[u8], mut i: usize, id: bool, mut f: impl FnMut(usize, usize)) -> usize {
    let (mut carry, mut open, mut skip) = (0, 0, id);
    loop {
        let (m, lf) = masks(data, i);
        let m = m & (lf & lf.wrapping_neg()).wrapping_sub(1);
        // The line's first token, its id, is no text token.
        let m = if skip { m & (m + 1) } else { m };
        skip = false;
        let after = m << 1 | carry;
        let (mut starts, mut ends) = (m & !after, !m & after);
        if carry != 0 && ends != 0 {
            // The first end is of the token from the previous 64 bytes.
            f(open, i + ends.trailing_zeros() as usize);
            ends &= ends - 1;
        }
        while ends != 0 {
            let (s, e) = (starts.trailing_zeros(), ends.trailing_zeros());
            f(i + s as usize, i + e as usize);
            (starts, ends) = (starts & (starts - 1), ends & (ends - 1));
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
    let b = data.get(i..i + 64).unwrap_or_else(|| {
        pad[..data.len() - i].copy_from_slice(&data[i..]);
        &pad
    });
    // The target is x86-64-v3 (AVX2).
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
}

/// Asks the CPU to start loading the cache line of `p`.
fn prefetch<T>(p: &T) {
    // _MM_HINT_T0
    unsafe { std::arch::x86_64::_mm_prefetch::<3>(p as *const T as *const i8) };
}

/// A chunk's posting lists: list l has the ids first + docs[offs[l]..offs[l + 1]];
/// its bitmap rows, `words` words each, of its own documents; and its phrase
/// matches as (query, id). A thread reuses one for all its chunks, so the
/// pages of its buffers are touched once.
#[derive(Default)]
struct Chunk {
    first: u32,
    words: usize,
    offs: Vec<u32>,
    docs: Vec<u16>,
    rows: Vec<u64>,
    hits: Vec<(u32, u32)>,
    stream: Vec<u16>,
}

/// The chunk-local ids of the documents in list l of c.
fn post(c: &Chunk, l: usize) -> &[u16] {
    &c.docs[c.offs[l] as usize..c.offs[l + 1] as usize]
}

/// Sets v's length to n, growing it to exactly n rather than doubling it.
fn grow<T: Copy + Default>(v: &mut Vec<T>, n: usize) {
    v.reserve_exact(n.saturating_sub(v.len()));
    v.resize(n, T::default());
}

/// Indexes the whole lines in data[lo..hi] (at least one); their first id is a multiple of 64.
fn scan_chunk(c: &mut Chunk, data: &[u8], lo: usize, hi: usize, plan: &Plan) {
    let last = data[..hi - 1].rsplit(|&b| b == b'\n').next().unwrap(); // the last line
    let (first, nl) = (id_at(data, lo), plan.nlist);
    let words = (id_at(last, 0) + 1 - first).div_ceil(64) as usize;
    let (rows, hits, docs, offs) = (&mut c.rows, &mut c.hits, &mut c.docs, &mut c.offs);
    grow(rows, plan.nbm * words); // every word is written
    // The list-term ids of each document, each document ended by u16::MAX.
    let stream = &mut c.stream;
    (c.first, c.words, _) = (first, words, (stream.clear(), hits.clear(), offs.clear()));
    stream.reserve_exact((hi - lo) / 16);
    // The bitmap words of the current 64 documents, stored when they are done,
    // and one for all other terms.
    let (mut doc, mut group) = (first, vec![0u64; plan.nbm + 1]);
    let flush = |rows: &mut [u64], group: &mut [u64], doc: u32| {
        for (b, x) in group[..plan.nbm].iter_mut().enumerate() {
            rows[b * words + (doc - first) as usize / 64] = std::mem::take(x);
        }
    };
    for_each_doc(&data[lo..hi], plan, |tokens, anch| {
        if doc % 64 == 0 && doc != first {
            flush(rows, &mut group, doc - 1);
        }
        // Branch-free: write every term and keep the list terms; a term
        // without a bitmap sets a bit in the spare group word.
        let (mut n, bit, base) = (0, 1u64 << (doc & 63), stream.len());
        stream.resize(base + tokens.len() + 1, u16::MAX);
        let (out, group) = (&mut stream[base..], &mut group[..plan.nbm + 1]);
        for &t in tokens {
            out[n] = t as u16;
            n += ((t as usize) < nl) as usize;
            group[(t as usize).wrapping_sub(nl).min(plan.nbm)] |= bit;
        }
        out[n] = u16::MAX;
        stream.truncate(base + n + 1);
        // Phrases: compare the tokens around each anchor with its phrases.
        for &(p, mut i) in anch {
            while let [q @ ..=0xffff_fffe, n, j, ..] = plan.phr[i..] {
                // q < u32::MAX: not the end marker.
                let (n, j) = (n as usize, j as usize);
                if p >= j && tokens.get(p - j..p - j + n) == Some(&plan.phr[i + 3..i + 3 + n]) {
                    hits.push((q, doc));
                }
                i += 3 + n;
            }
        }
        doc += 1;
    });
    flush(rows, &mut group, doc - 1);
    assert!(doc - first <= 1 << 16, "chunk too large");
    // Counting sort of the stream. offs[l + 2] counts list l, then offs[l + 1] is
    // where its next id goes, and after the fill offs[l] is where list l starts.
    offs.resize(nl + 2, 0);
    for &l in stream.iter().filter(|&&l| l != u16::MAX) {
        offs[l as usize + 2] += 1;
    }
    (2..offs.len()).for_each(|l| offs[l] += offs[l - 1]);
    grow(docs, offs[nl + 1] as usize);
    let mut d = 0u16;
    for &l in stream.iter() {
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
            (docs[w], w) = (docs[i], w + (i == a || docs[i] != docs[i - 1]) as usize);
        }
    }
    offs[nl] = w as u32;
    hits.sort_unstable();
    hits.dedup(); // a phrase can occur twice in a document
}

/// A query's answer: count << 44 | id sum; the last of the ten smallest ids;
/// and the ten smallest ids, sorted, padded with u32::MAX. With at most
/// 250,000 documents, count fits the high 20 bits and id sum the low 44 bits.
/// Queries occupy separate cache lines.
#[repr(align(64))]
struct Acc(AtomicU64, AtomicU32, Mutex<[u32; 10]>);

impl Acc {
    /// Adds n ids of a chunk, first + the ids in `top`, sorted, with id sum `sum`.
    fn add(&self, first: u32, n: u64, sum: u64, top: impl Iterator<Item = u32>) {
        if n == 0 {
            return;
        }
        self.0.fetch_add(n << 44 | n * first as u64 + sum, Relaxed); // the sum fits 44 bits
        if first < self.1.load(Relaxed) {
            // Merge the new ids into the sorted ten.
            let (t, mut i) = (&mut *self.2.lock().unwrap(), 0);
            let (old, mut top) = (*t, top.map(|d| first + d).peekable());
            for x in t.iter_mut() {
                let new = top.next_if(|&d| d < old[i]);
                *x = new.unwrap_or_else(|| (old[i], i += 1).0);
            }
            self.1.store(t[9], Relaxed);
        }
    }

    /// Adds the ids first + d, which are sorted.
    fn add_sorted(&self, first: u32, d: impl ExactSizeIterator<Item = u32> + Clone) {
        self.add(first, d.len() as u64, d.clone().map(u64::from).sum(), d)
    }
}

/// Answers a BOOL query strictly left to right. The running result is a sorted
/// list `r` until a large set is ORed in, then the bitmap `bm`, which is all
/// zero whenever it is not in use.
fn boolean(q: &[(u8, u32)], plan: &Plan, c: &Chunk, s: &mut Scratch, acc: &Acc) {
    let (words, (r, o, bm)) = (c.words, s);
    let (mut is_bm, bm) = (false, &mut bm[..words]);
    r.clear();
    let get = |b: &[u64], d: u16| b[d as usize / 64] >> (d & 63) & 1 != 0;
    let set = |b: &mut [u64], d: u16| b[d as usize / 64] |= 1 << (d & 63);
    let clear = |b: &mut [u64], d: u16| b[d as usize / 64] &= !(1 << (d & 63));
    for &(op, t) in q {
        let (t, and) = (t as usize, op == b'A');
        if !is_bm && r.is_empty() && (and || op == b'N') {
            continue; // the result stays empty
        }
        if t >= plan.nlist {
            let row = &c.rows[(t - plan.nlist) * words..][..words];
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
        let p = post(c, t);
        if !is_bm && (and || op == b'N') && r.len() * 16 < p.len() {
            // Look the few ids of r up in the term's list.
            r.retain(|d| p.binary_search(d).is_ok() == and);
            continue;
        }
        if op == 0 {
            r.extend_from_slice(p); // the first term
            continue;
        }
        if !is_bm && op == b'O' && r.len() + p.len() > words / 4 {
            r.drain(..).for_each(|d| set(bm, d));
            is_bm = true;
        }
        let pl = p.iter().copied();
        match (is_bm, op) {
            (true, b'A') => {
                r.extend(pl.filter(|&d| get(bm, d)));
                bm.fill(0);
                is_bm = false;
            }
            (true, b'N') => pl.for_each(|d| clear(bm, d)),
            (true, _) => pl.for_each(|d| set(bm, d)),
            (false, b'A') if p.len() * 16 < r.len() => {
                o.clear();
                o.extend(pl.filter(|d| r.binary_search(d).is_ok()));
                std::mem::swap(r, o);
            }
            (false, b'A' | b'N') => {
                pl.for_each(|d| set(bm, d));
                r.retain(|&d| get(bm, d) == and);
                p.iter().for_each(|&d| bm[d as usize / 64] = 0);
            }
            _ => {
                // Merge the sorted lists r and p.
                let (mut i, mut j) = (0, 0);
                o.clear();
                while i < r.len() && j < p.len() {
                    let (a, b) = (r[i], p[j]);
                    o.push(a.min(b));
                    i += (a <= b) as usize;
                    j += (b <= a) as usize;
                }
                o.extend_from_slice(&r[i..]);
                o.extend_from_slice(&p[j..]);
                std::mem::swap(r, o);
            }
        }
    }
    if !is_bm {
        return acc.add_sorted(c.first, r.iter().map(|&d| d as u32));
    }
    // Count, id sum and the first ten ids.
    let (n, sum) = count_sum(bm);
    let ids = bm.iter().enumerate().filter(|(_, &x)| x != 0);
    let bits = |x: u64| (0..64).filter(move |b| x >> b & 1 != 0);
    let ids = ids.flat_map(|(i, &x)| bits(x).map(move |b| (i * 64 + b) as u32));
    acc.add(c.first, n, sum, ids);
    bm.fill(0);
}

/// The number of set bits in the words b and the sum of their positions.
fn count_sum(b: &[u64]) -> (u64, u64) {
    let (mut n, mut sum) = (0, 0);
    unsafe {
        use std::arch::x86_64::*;
        let lut = |t: [i8; 16]| _mm256_broadcastsi128_si256(_mm_loadu_si128(t.as_ptr().cast()));
        // Of each nibble value: its set bits, and the sum of their positions.
        let cnt = lut([0, 1, 1, 2, 1, 2, 2, 3, 1, 2, 2, 3, 2, 3, 3, 4]);
        let pos = lut([0, 0, 1, 1, 2, 2, 3, 3, 3, 3, 4, 4, 5, 5, 6, 6]);
        let idx = _mm256_set1_epi64x(0x0706050403020100); // each byte's index in its word
        let (nib, z) = (_mm256_set1_epi8(15), _mm256_setzero_si256());
        let (one, low) = (_mm256_set1_epi16(1), _mm256_set1_epi64x(!0u32 as i64));
        let (mut vn, mut vs, mut base) = (z, z, _mm256_setr_epi64x(0, 64, 128, 192));
        for w in b.chunks_exact(4) {
            let v = _mm256_loadu_si256(w.as_ptr().cast());
            let lo = _mm256_and_si256(v, nib);
            let hi = _mm256_and_si256(_mm256_srli_epi16(v, 4), nib);
            let ch = _mm256_shuffle_epi8(cnt, hi);
            let c = _mm256_add_epi8(_mm256_shuffle_epi8(cnt, lo), ch); // set bits of each byte
            let p = _mm256_add_epi8(_mm256_shuffle_epi8(pos, lo), _mm256_shuffle_epi8(pos, hi));
            let p = _mm256_sad_epu8(_mm256_add_epi8(p, _mm256_slli_epi16(ch, 2)), z); // in its bytes
            // Each byte's index in its word times its set bits, summed per word.
            let j = _mm256_madd_epi16(_mm256_maddubs_epi16(c, idx), one);
            let j = _mm256_add_epi64(_mm256_srli_epi64(j, 32), _mm256_and_si256(j, low));
            let wc = _mm256_sad_epu8(c, z);
            let s = _mm256_add_epi64(p, _mm256_slli_epi64(j, 3));
            let s = _mm256_add_epi64(s, _mm256_mul_epu32(wc, base));
            (vn, vs) = (_mm256_add_epi64(vn, wc), _mm256_add_epi64(vs, s));
            base = _mm256_add_epi64(base, _mm256_set1_epi64x(256));
        }
        let h = |v: __m256i| -> u64 { std::mem::transmute::<_, [u64; 4]>(v).iter().sum() };
        (n, sum) = (n + h(vn), sum + h(vs));
    }
    // The words the vector loop left. The positions of the set bits of x sum
    // to the sum over k of 2^k times the count of those with bit k.
    for (i, &x) in b.iter().enumerate().skip(b.len() / 4 * 4) {
        let pos = (0..6).map(|k| ((x & !(!0 / ((1 << (1 << k)) + 1))).count_ones() as u64) << k);
        n += x.count_ones() as u64;
        sum += (i * 64) as u64 * x.count_ones() as u64 + pos.sum::<u64>();
    }
    (n, sum)
}

/// Answers the queries in the chunk c: the BOOL queries whose trigger terms
/// it has, and the phrases it matches.
fn answer(c: &Chunk, plan: &Plan, (trig, toff, acc): &Late, s: &mut Scratch) {
    // Chunks start at different queries, so threads seldom update the same one at once.
    let from = (c.first as usize).wrapping_mul(0x9e37_79b9) % acc.len().max(1);
    for qi in (from..acc.len()).chain(0..from) {
        let trig = &trig[toff[qi] as usize..toff[qi + 1] as usize];
        let has = |&t: &u32| t as usize >= plan.nlist || !post(c, t as usize).is_empty();
        if trig.iter().any(has) {
            let q = &plan.terms[plan.qs[qi].1 as usize..plan.qs[qi + 1].1 as usize];
            boolean(q, plan, c, s, &acc[qi]);
        }
    }
    for h in c.hits.chunk_by(|a, b| a.0 == b.0) {
        acc[h[0].0 as usize].add_sorted(0, h.iter().map(|h| h.1));
    }
}

/// Per-thread buffers for answering queries: the running result as a sorted
/// list, a second list, and the running result as a bitmap.
type Scratch = (Vec<u16>, Vec<u16>, Vec<u64>);

/// The id of the line that starts at byte i.
fn id_at(data: &[u8], i: usize) -> u32 {
    let digits = data[i..].iter().take_while(|&&b| b != b'\t');
    digits.fold(0, |n, &b| n * 10 + (b - b'0') as u32)
}

// std has no mmap; libc is always linked.
extern "C" {
    fn mmap(addr: *mut u8, len: usize, prot: i32, flags: i32, fd: i32, off: i64) -> *mut u8;
    fn madvise(addr: *mut u8, len: usize, advice: i32) -> i32;
    fn munmap(addr: *mut u8, len: usize) -> i32;
}

/// Maps a read-only file into memory.
fn map_file(path: &str) -> &'static [u8] {
    let f = fs::File::open(path).expect("open input");
    let len = f.metadata().unwrap().len() as usize;
    // PROT_READ = 1, MAP_PRIVATE = 2 on Linux.
    let p = unsafe { mmap(std::ptr::null_mut(), len, 1, 2, f.as_raw_fd(), 0) };
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
fn par<T: Send>(n: usize, f: &(impl Fn(usize) -> T + Sync)) -> Vec<T> {
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
    let data_dir = std::env::var("SD_DATA").unwrap_or_else(|_| "/data".into());
    let out_dir = std::env::var("SD_OUT").unwrap_or_else(|_| "/out".into());
    let n = thread::available_parallelism().map_or(4, |n| n.get());
    let nthreads = std::env::var("SD_THREADS").map_or(n, |s| s.parse().unwrap_or(n));

    let qtext = map_file(&format!("{data_dir}/queries.txt"));
    let mut plan = Plan::default();
    // Term 0 stands for every token no query uses; empty slots hold it.
    resize((qtext.len() / 16 | 64).next_power_of_two(), &mut plan); // rarely grows
    // Query words: BOOL and PHRASE start a query, AND, OR and NOT are
    // operators and terms are lowercase. Query i is (b'B' or b'P', its first
    // term), its terms terms[qs[i].1..qs[i + 1].1] as (first byte of the
    // operator: AND, NOT, else OR; term); the first term of a BOOL query has
    // operator 0, OR on the empty set. Each thread parses a part of whole
    // lines and interns its terms into the shared table in batches, their
    // slots prefetched first, so that the table's cache misses overlap. A
    // slot's last word is 0 while empty, 1 while being filled, then 2. The
    // threads take new ids in blocks of 256 from `ids`; `own` is a thread's
    // next one, at the end of its block if a multiple of 256. A thread marks
    // the terms of BOOL queries in `role`, which has room for every id.
    let (ids, long) = (AtomicU32::new(256), Mutex::new(HashMap::new()));
    let tbl = unsafe { &*(&mut *plan.keys as *mut [[u64; 4]] as *const [[AtomicU64; 4]]) };
    let mut role = vec![0u8; qtext.len() / 2 + 256 * (nthreads + 1)];
    let roles = unsafe { &*(&mut role[..] as *mut [u8] as *const [AtomicU8]) };
    let new = |own: &mut u32| {
        if *own % 256 == 0 {
            *own = ids.fetch_add(256, Relaxed);
        }
        *own += 1;
        *own as u64 - 1
    };
    let intern = |own: &mut u32, s: usize, e: usize| {
        if e - s > 16 {
            let w = qtext[s..e].to_vec();
            return *long.lock().unwrap().entry(w).or_insert_with(|| new(own)) as u32;
        }
        let (k, h) = (key(qtext, s, e - s), hash(key(qtext, s, e - s)));
        for x in (h..h + tbl.len()).map(|i| &tbl[i & (tbl.len() - 1)]) {
            if x[3].load(Acquire) == 0 && x[3].compare_exchange(0, 1, Acquire, Acquire).is_ok() {
                for (y, v) in x.iter().zip([k[0], k[1], new(own)]) {
                    y.store(v, Relaxed);
                }
                x[3].store(2, Release);
            }
            while x[3].load(Acquire) == 1 {}
            if x[0].load(Relaxed) == k[0] && x[1].load(Relaxed) == k[1] {
                return x[2].load(Relaxed) as u32;
            }
        }
        unreachable!()
    };
    let parts = par(nthreads, &|k| {
        let (mut qs, mut terms, mut op, mut batch, mut own) = (vec![], vec![], 0, vec![], 0);
        let part = |k| line_start(qtext, k * qtext.len() / nthreads);
        let (mut i, end) = (part(k), part(k + 1));
        while i < end {
            i = each_token(qtext, i, false, |s, e| match qtext[s] {
                b'B' | b'P' => qs.push((qtext[s], (terms.len() + batch.len()) as u32)),
                b'A' | b'O' | b'N' => op = qtext[s],
                _ => batch.push((std::mem::take(&mut op), s, e, qs.last().unwrap().0)),
            });
            if batch.len() >= 64 || i >= end {
                for &(_, s, e, _) in &batch {
                    prefetch(&tbl[hash(key(qtext, s, e - s)) & (tbl.len() - 1)]);
                }
                for (op, s, e, q) in batch.drain(..) {
                    terms.push((op, intern(&mut own, s, e)));
                    if q == b'B' {
                        roles[terms.last().unwrap().1 as usize].store(1, Relaxed);
                    }
                }
            }
        }
        (qs, terms)
    });
    plan.long = long.into_inner().unwrap();
    role.truncate(ids.into_inner() as usize);
    if plan.keys.iter().filter(|e| e[0] != 0).count() * 3 >= plan.keys.len() * 2 {
        resize(plan.keys.len() * 2, &mut plan); // at most two thirds full
    }
    let data = map_file(&format!("{data_dir}/docs.txt"));

    // Anchor each phrase on its rarest term in a sample of the corpus.
    // freq[t]: sample documents with the term t. The threads list the terms
    // of each document in their parts of the sample, without repeats.
    // Meanwhile another thread joins the queries and terms of the parts,
    // and one more thread rebuilds the table without collisions.
    let (n, sample) = (role.len(), &data[..line_start(data, 1 << 19)]); // 512 KiB
    let join = |parts: Vec<(Vec<_>, Vec<_>)>| {
        let (mut qs, mut terms) = (Vec::new(), Vec::new());
        for (q, t) in parts {
            qs.extend(q.iter().map(|&(b, j)| (b, j + terms.len() as u32)));
            terms.extend(t);
        }
        qs.push((0, terms.len() as u32));
        (qs.len() - 1, qs, terms)
    };
    let old: &'static [[u64; 4]] = unsafe { &*(&*plan.keys as *const [[u64; 4]]) };
    let mut t = Plan::default();
    t.keys = std::mem::take(&mut plan.keys);
    let perfect = thread::spawn(move || (perfect(&mut t), (t.keys, t.disp)).1);
    let ((nq, qs, mut terms), parts) = thread::scope(|s| {
        let joined = s.spawn(|| join(parts));
        // The sample's term ids, from the old table.
        let long = |w: &[u8]| *plan.long.get(&w.to_ascii_lowercase()).unwrap_or(&0) as u32;
        let lin = |s: usize, e: usize| match (e - s, key(sample, s, e - s)) {
            (17.., _) => long(&sample[s..e]),
            (_, k) => old[slot(old, k)][2] as u32,
        };
        let counts = par(nthreads, &|k| {
            let (mut v, mut d, mut doc) = (Vec::new(), 0, Vec::new());
            let part = |k| line_start(sample, k * sample.len() / nthreads);
            let mut i = part(k);
            while i < part(k + 1) {
                i = each_token(sample, i, true, |s, e| doc.push(lin(s, e)));
                (doc.sort_unstable(), doc.dedup());
                v.extend(doc.drain(..));
                d += 1;
            }
            (v, d)
        });
        (joined.join().unwrap(), counts)
    });
    let (mut freq, sdocs) = (vec![0; n], parts.iter().map(|p| p.1).sum::<i32>());
    for (v, _) in parts {
        v.iter().for_each(|&t: &u32| freq[t as usize] += 1);
    }
    // Each phrase as (its rarest term, the anchor; query; anchor position),
    // sorted by anchor, found by another thread meanwhile.
    let query = |i: usize| &terms[qs[i].1 as usize..qs[i + 1].1 as usize];
    let (list, (new, df)) = thread::scope(|s| {
        let list = s.spawn(|| {
            let mut list = Vec::new();
            for qi in (0..nq).filter(|&i| qs[i].0 == b'P') {
                let p = query(qi);
                let j = (0..p.len()).min_by_key(|&j| freq[p[j].1 as usize]).unwrap();
                list.push((p[j].1, qi as u32, j as u32));
            }
            list.sort_unstable_by_key(|a| a.0);
            list
        });
        // A BOOL term in more than 1 of 32 sample documents gets a bitmap,
        // and so do the most frequent others beyond 65,535.
        let mut bools: Vec<usize> = (0..n).filter(|&t| role[t] != 0).collect();
        bools.sort_unstable_by_key(|&t| std::cmp::Reverse(freq[t]));
        let common = bools.partition_point(|&t| freq[t] as usize * 32 > sdocs as usize);
        let nbm = common.max(bools.len().saturating_sub(65535));
        (plan.nlist, plan.nbm) = (bools.len() - nbm, nbm);
        // Renumber the terms: list terms first, then bitmap terms, then the rest.
        let (mut new, mut df) = (vec![0; n], vec![0; n]);
        let rest = (0..n).filter(|&t| role[t] == 0);
        let lists = bools[nbm..].iter().chain(&bools[..nbm]);
        for (i, t) in lists.copied().chain(rest).enumerate() {
            (new[t], df[i]) = (i as u32, freq[t]);
        }
        (list.join().unwrap(), (new, df))
    });
    // The phrases by anchor, as (query, length, anchor position, terms); each
    // anchor's end with u32::MAX, and its start + 1 in the high half of its value.
    let mut start = vec![0u32; n];
    plan.phr.reserve(list.len() * 14);
    for g in list.chunk_by(|a, b| a.0 == b.0) {
        start[g[0].0 as usize] = plan.phr.len() as u32 + 1;
        for &(_, qi, j) in g {
            let p = query(qi as usize);
            plan.phr.extend([qi, p.len() as u32, j]);
            plan.phr.extend(p.iter().map(|e| new[e.1 as usize]));
        }
        plan.phr.extend([u32::MAX; 3]);
    }
    (plan.keys, plan.disp) = perfect.join().unwrap();
    unsafe { munmap(old.as_ptr() as *mut u8, old.len() * 32) };
    // One pass gives each term its new number and its phrases' start.
    let remap = |t: u64| new[t as usize] as u64 | (start[t as usize] as u64) << 32;
    plan.keys.iter_mut().for_each(|e| e[2] = remap(e[2]));
    plan.long.values_mut().for_each(|t| *t = remap(*t));
    terms.iter_mut().for_each(|e| e.1 = new[e.1 as usize]);
    drop((qtext, freq, new, start)); // the scan uses none of these

    (plan.qs, plan.terms) = (qs, terms);
    // Equal byte ranges, each moved to the next line whose id is a multiple
    // of 64; at most 65,536 lines per chunk.
    let nchunks = nthreads * data.len().div_ceil(nthreads << 24).max(1);
    let cut = |k| {
        let mut i = line_start(data, k * data.len() / nchunks);
        while i < data.len() && id_at(data, i) % 64 != 0 {
            i = line_start(data, i + 1);
        }
        i
    };
    // The threads take the chunks in turn; each indexes its chunk, adds the
    // chunk's answers to every query's and reuses its buffers for the next.
    // Meanwhile one more thread sets up what answering needs.
    let (next, late) = (AtomicUsize::new(0), std::sync::OnceLock::new());
    let query = |i: usize| &plan.terms[plan.qs[i].1 as usize..plan.qs[i + 1].1 as usize];
    let d = |t| df[t as usize];
    par(nthreads + 1, &|k| {
        if k == nthreads {
            // Trigger terms: a list of terms whose sets hold the result so far, kept
            // through NOT, extended by OR, and swapped for the AND term if that is rarer.
            let (mut trig, mut toff) = (Vec::new(), vec![0]);
            for qi in 0..nq {
                let (from, mut est) = (trig.len(), 0);
                for &(op, t) in query(qi).iter().filter(|_| plan.qs[qi].0 == b'B') {
                    match op {
                        b'A' if d(t) < est => (trig.truncate(from), trig.push(t), est = d(t)).1,
                        b'A' | b'N' => {}
                        _ => (trig.push(t), est += d(t)).1,
                    }
                }
                toff.push(trig.len() as u32);
            }
            let acc = (0..nq).map(|_| Acc(0.into(), (!0).into(), Mutex::new([!0; 10])));
            _ = late.set((trig, toff, acc.collect()));
            return;
        }
        let (mut s, mut c): (Scratch, _) = ((vec![], vec![], vec![0; 1024]), Chunk::default());
        let chunks = (0..).map(|_| next.fetch_add(1, Relaxed));
        for k in chunks.take_while(|&k| k < nchunks) {
            let (lo, hi) = (cut(k), cut(k + 1));
            if lo < hi {
                scan_chunk(&mut c, data, lo, hi, &plan);
                answer(&c, &plan, late.wait(), &mut s);
            }
        }
    });
    let acc = &late.get().unwrap().2;
    // The answer lines, in blocks of queries.
    let per = nq.div_ceil(nthreads).max(1);
    let outs = par(nthreads, &|k| {
        let mut out = String::new();
        for a in acc.iter().skip(k * per).take(per) {
            let ns = a.0.load(Relaxed);
            write!(out, "{} {}", ns >> 44, ns & ((1 << 44) - 1)).unwrap();
            for d in a.2.lock().unwrap().iter().take_while(|&&d| d != u32::MAX) {
                write!(out, " {d}").unwrap();
            }
            out.push('\n');
        }
        out
    });
    fs::create_dir_all(&out_dir).ok();
    let mut f = fs::File::create(format!("{out_dir}/results.txt")).expect("create results.txt");
    outs.iter().for_each(|o| f.write_all(o.as_bytes()).unwrap());
    std::process::exit(0); // the OS frees everything faster than the destructors
}
