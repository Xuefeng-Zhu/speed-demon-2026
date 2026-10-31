//! Speed Demon 2026, Track B (Index). Standard library only.
//!
//! 1. Parse the queries first and intern every term they use. Each phrase is
//!    anchored on its rarest term, judged from a small sample of the corpus.
//! 2. Map docs.txt and split it into one chunk of whole lines per core. Each
//!    thread tokenizes its chunk once: BOOL terms get posting lists, phrases
//!    are checked right there around each anchor occurrence. Then it answers
//!    every BOOL query on its own documents with a bitmap of the chunk.
//! 3. Chunks hold ascending, disjoint id ranges, so the answers merge in order.

use std::fmt::Write as _;
use std::{collections::HashMap, env, fs, thread};

/// Term id of a token that no query uses.
const MISS: u32 = u32::MAX;
/// A term with df > ndocs / DENSE is used as a bitmap rather than a list.
const DENSE: usize = 32;
/// Bytes of corpus read up front to estimate which phrase term is rarest.
const SAMPLE: usize = 1 << 19;
/// Bytes of corpus a thread scans between releasing what it has read.
const SLICE: usize = 1 << 22;
/// Term roles: used by a BOOL query and gets a posting list; anchors a
/// phrase; used by a BOOL query and common, so it gets a bitmap instead.
const IN_BOOL: u8 = 1;
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
/// term id, and what the corpus scan does with each term: its roles, and the
/// phrases it anchors, anchors[aoff[t]..aoff[t + 1]] for term t, as (query,
/// start of the phrase in `flat`, its length, position of the term in it).
/// BITMAP term t has bitmap brow[t]; bitmap i is that of term bterms[i].
#[derive(Default)]
struct Plan<'q> {
    queries: &'q [Query],
    slots: Vec<u32>,
    keys: Vec<Key>,
    role: Vec<u8>,
    aoff: Vec<u32>,
    anchors: Vec<(u32, u32, u32, u32)>,
    flat: Vec<u32>,
    brow: Vec<u32>,
    bterms: Vec<u32>,
}

impl Plan<'_> {
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

enum Query {
    Bool(Vec<(u8, u32)>), // (first byte of the operator: AND, NOT, else OR; term)
    Phrase(Vec<u32>),
}

/// What one chunk found for each query: (match count, start of its first
/// min(count, 10) ids in the second vector, id sum).
type Answers = (Vec<(u32, u32, u64)>, Vec<u32>);

/// Summarizes the ascending chunk-local `ids`; their first ten go to `top`.
fn part(first: u32, ids: impl Iterator<Item = u32>, top: &mut Vec<u32>) -> (u32, u32, u64) {
    let start = top.len() as u32;
    let (n, sum) = ids.fold((0, 0), |(n, sum), d| {
        top.extend((n < 10).then_some(first + d));
        (n + 1, sum + (first + d) as u64)
    });
    (n, start, sum)
}

/// Indexes the whole lines in data[lo..hi] and answers every query on them.
/// Doc ids are local to the chunk until `part` adds the id of its first line.
fn solve_chunk(data: &[u8], lo: usize, hi: usize, plan: &Plan) -> Answers {
    let digits = data[lo..].iter().take_while(|&&b| b != b'\t');
    let first = digits.fold(0, |n, &b| n * 10 + (b - b'0') as u32);
    let nterms = plan.role.len();
    // The BOOL-term ids of each document, MISS-terminated. A term occurring
    // twice is listed twice; its posting list then repeats the doc, which
    // the bitmap operations below do not mind.
    let mut stream = Vec::with_capacity((hi - lo) / 16);
    let mut hits = HashMap::<usize, Vec<u32>>::new(); // phrase matches by query
    let (mut ndocs, mut new, mut anch, mut bm) = (0usize, Vec::new(), Vec::new(), Vec::new());
    // Bitmaps of the BITMAP terms, interleaved: word w of bitmap i is at blocks[w * nb + i].
    let (nb, mut blocks) = (plan.bterms.len(), Vec::new());
    for_each_doc(data, lo, hi, plan, |tokens| {
        let doc = ndocs as u32;
        // Branch-free: write every term, keep the BOOL terms,
        // and note where the anchors and the BITMAP terms are.
        new.resize(tokens.len(), 0);
        anch.resize(tokens.len(), 0);
        bm.resize(tokens.len(), 0);
        let (mut n, mut m, mut k) = (0, 0, 0);
        for (p, &t) in tokens.iter().enumerate() {
            let role = plan.role[t as usize];
            (new[n], anch[m], bm[k]) = (t, p, t);
            n += (role & IN_BOOL != 0) as usize;
            m += (role & ANCHOR != 0) as usize;
            k += (role & BITMAP != 0) as usize;
        }
        stream.extend_from_slice(&new[..n]);
        stream.push(MISS);
        ndocs += 1;
        let base = (doc as usize >> 6) * nb;
        blocks.resize(base + nb, 0);
        for &t in &bm[..k] {
            blocks[base + plan.brow[t as usize] as usize] |= 1 << (doc & 63);
        }
        // Phrases: compare the tokens around each anchor with its phrases.
        for &p in &anch[..m] {
            let t = tokens[p] as usize;
            for &(q, s, n, j) in &plan.anchors[plan.aoff[t] as usize..plan.aoff[t + 1] as usize] {
                let (s, n, j) = (s as usize, n as usize, j as usize);
                if p >= j && tokens.get(p - j..p - j + n) == Some(&plan.flat[s..s + n]) {
                    hits.entry(q as usize).or_default().push(doc);
                }
            }
        }
    });
    // Counting sort of the stream into CSR: term t owns docs[offs[t]..offs[t + 1]].
    let mut offs = vec![0u32; nterms + 1];
    stream
        .iter()
        .filter(|&&t| t != MISS)
        .for_each(|&t| offs[t as usize + 1] += 1);
    (1..=nterms).for_each(|t| offs[t] += offs[t - 1]);
    let (mut cur, mut docs, mut d) = (offs.clone(), vec![0u32; offs[nterms] as usize], 0);
    for t in stream {
        if t == MISS {
            d += 1;
        } else {
            docs[cur[t as usize] as usize] = d;
            cur[t as usize] += 1;
        }
    }

    drop(cur);

    // BOOL queries: strictly left-to-right set algebra on the bitmap `r`.
    // Bitmaps of frequent terms: of the BITMAP terms, and others built on first use.
    let words = ndocs.div_ceil(64);
    let (mut r, mut tmp) = (vec![0u64; words], vec![0u64; words]);
    let row = |(i, &t): (usize, &u32)| (t, (0..words).map(|w| blocks[w * nb + i]).collect());
    let mut dense: HashMap<u32, Vec<u64>> = plan.bterms.iter().enumerate().map(row).collect();
    drop(blocks);
    let bit = |d: &u32| (*d as usize >> 6, 1u64 << (d & 63));
    let mut top = Vec::new();
    let answer = |qi: usize| {
        let Query::Bool(q) = &plan.queries[qi] else {
            let mut docs = hits.remove(&qi).unwrap_or_default();
            docs.dedup(); // a phrase can occur twice in a document
            return part(first, docs.into_iter(), &mut top);
        };
        for &(op, t) in q {
            let apply = |x: &mut u64, y: u64| match op {
                b'A' => *x &= y,
                b'N' => *x &= !y,
                _ => *x |= y,
            };
            let post = &docs[offs[t as usize] as usize..offs[t as usize + 1] as usize];
            if plan.role[t as usize] & BITMAP != 0 || post.len() * DENSE > ndocs {
                let b = dense.entry(t).or_insert_with(|| {
                    let mut b = vec![0u64; words];
                    post.iter().map(bit).for_each(|(w, m)| b[w] |= m);
                    b
                });
                r.iter_mut().zip(&*b).for_each(|(x, &y)| apply(x, y));
            } else if op == b'A' {
                tmp.fill(0);
                post.iter().map(bit).for_each(|(w, m)| tmp[w] |= r[w] & m);
                std::mem::swap(&mut r, &mut tmp);
            } else {
                post.iter().map(bit).for_each(|(w, m)| apply(&mut r[w], m));
            }
        }
        // Count, id sum and the first ten ids, eight zero words skipped at a
        // time; clears `r` for the next query. The positions of the set bits
        // of x sum to the sum over k of 2^k times the count of those with bit k.
        let (start, mut n, mut sum) = (top.len(), 0, 0);
        for (i, c) in r.chunks_mut(8).enumerate() {
            if c.iter().fold(0, |a, x| a | x) == 0 {
                continue;
            }
            for (j, x) in c.iter_mut().enumerate() {
                let x = std::mem::take(x);
                let id = (first as usize + (i * 8 + j) * 64) as u64;
                let mut y = x;
                while y != 0 && top.len() < start + 10 {
                    top.push(id as u32 + y.trailing_zeros());
                    y &= y - 1;
                }
                let pos =
                    (0..6).map(|k| ((x & !(!0 / ((1 << (1 << k)) + 1))).count_ones() as u64) << k);
                n += x.count_ones();
                sum += id * x.count_ones() as u64 + pos.sum::<u64>();
            }
        }
        (n, start as u32, sum)
    };
    let counts = (0..plan.queries.len()).map(answer).collect();
    (counts, top)
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
    let nthreads = thread::available_parallelism().map_or(4, |n| n.get());

    let qtext = fs::read(format!("{data_dir}/queries.txt")).expect("read queries.txt");
    // Each term follows a space, so the table stays at most half full.
    let mut plan = Plan {
        slots: vec![MISS; (2 * qtext.iter().filter(|&&b| b == b' ').count()).next_power_of_two()],
        ..Default::default()
    };
    // Terms are first numbered by occurrence. Interning them all in one loop
    // lets it prefetch the slots of the terms ahead.
    let (mut queries, mut occ) = (Vec::new(), Vec::new());
    let at = |w: &[u8]| w.as_ptr() as usize - qtext.as_ptr() as usize;
    let mut term = |w: &[u8], role| {
        occ.push((at(w), w.len(), role));
        occ.len() as u32 - 1
    };
    for line in qtext.split(|&b| b == b'\n').filter(|l| !l.is_empty()) {
        let mut w = line.split(|&b| b == b' ');
        queries.push(if line.starts_with(b"BOOL") {
            // (operator, term) pairs; the leading "BOOL" acts as OR on the empty set.
            let pair = || Some((w.next()?[0], term(w.next()?, IN_BOOL)));
            Query::Bool(std::iter::from_fn(pair).collect())
        } else {
            let terms = line[b"PHRASE \"".len()..line.len() - 1].split(|&b| b == b' ');
            Query::Phrase(terms.map(|w| term(w, 0)).collect())
        });
    }
    let mut ids = Vec::with_capacity(occ.len());
    for (i, &(s, n, role)) in occ.iter().enumerate() {
        _ = occ
            .get(i + 16)
            .map(|&(s, n, _)| prefetch(&plan.slots[plan.hash(&key(&qtext, s, n))]));
        ids.push(plan.intern(key(&qtext, s, n), role));
    }
    for q in &mut queries {
        match q {
            Query::Bool(v) => v.iter_mut().for_each(|(_, t)| *t = ids[*t as usize]),
            Query::Phrase(p) => p.iter_mut().for_each(|t| *t = ids[*t as usize]),
        }
    }
    drop((occ, ids));
    let data = map_file(&format!("{data_dir}/docs.txt"));

    // Anchor each phrase on its rarest term in a sample of the corpus.
    plan.queries = &queries;
    // The id of every token no query uses: a term with no role.
    plan.role.push(0);
    let (mut freq, mut sdocs) = (vec![0u32; plan.role.len()], 0);
    for_each_doc(data, 0, line_start(data, SAMPLE), &plan, |tokens| {
        sdocs += 1;
        tokens.iter().for_each(|&t| freq[t as usize] += 1);
    });
    // A BOOL term seen more than once per 64 sample documents gets a bitmap.
    plan.brow = vec![MISS; plan.role.len()];
    for t in 0..plan.keys.len() {
        if plan.role[t] & IN_BOOL != 0 && freq[t] as usize * 64 > sdocs {
            plan.role[t] ^= IN_BOOL | BITMAP;
            plan.brow[t] = plan.bterms.len() as u32;
            plan.bterms.push(t as u32);
        }
    }
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

    // Equal byte ranges, each moved to just after an LF.
    let cut = |k| line_start(data, k * data.len() / nthreads);
    let parts = par(nthreads, |k| solve_chunk(data, cut(k), cut(k + 1), &plan));
    // Merge and format the answers, one block of queries per thread.
    let format = |qs: std::ops::Range<usize>| {
        let mut out = String::new();
        for qi in qs {
            let n: u32 = parts.iter().map(|(c, _)| c[qi].0).sum();
            let sum: u64 = parts.iter().map(|(c, _)| c[qi].2).sum();
            write!(out, "{n} {sum}").unwrap();
            let top = parts
                .iter()
                .flat_map(|(c, ids)| &ids[c[qi].1 as usize..][..c[qi].0.min(10) as usize]);
            for d in top.take(10) {
                write!(out, " {d}").unwrap();
            }
            out.push('\n');
        }
        out
    };
    let (nq, block) = (queries.len(), queries.len().div_ceil(nthreads));
    let outs = par(nthreads, |k| format(k * block..((k + 1) * block).min(nq)));
    fs::create_dir_all(&out_dir).ok();
    fs::write(format!("{out_dir}/results.txt"), outs.concat()).expect("write results.txt");
}
