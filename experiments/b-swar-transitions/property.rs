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
use std::{collections::HashMap, env, fs, sync::Barrier, thread};

/// Term id of a token that no query uses.
const MISS: u32 = u32::MAX;
/// A term with df > ndocs / DENSE is used as a bitmap rather than a list.
const DENSE: usize = 32;
/// Bytes of corpus read up front to estimate which phrase term is rarest.
const SAMPLE: usize = 1 << 19;
/// Bytes of corpus a thread scans between releasing what it has read.
const SLICE: usize = 1 << 22;
/// Term roles: used by a BOOL query; anchors a phrase.
const IN_BOOL: u8 = 1;
const ANCHOR: u8 = 2;

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
/// phrases it anchors as (query index, phrase, position of the term in it).
#[derive(Default)]
struct Plan<'q> {
    queries: &'q [Query],
    phrases: &'q [Vec<u32>],
    slots: Vec<u32>,
    keys: Vec<Key>,
    role: Vec<u8>,
    anchors: Vec<Vec<(usize, &'q [u32], usize)>>,
}

impl Plan<'_> {
    fn slot(&self, k: &Key) -> (usize, u32) {
        let mut h = 0x9e37_79b9_7f4a_7c15u64;
        for word in k.0 { h ^= word; h = h.wrapping_mul(0xbf58_476d_1ce4_e5b9); h ^= h >> 29; }
        let mask = self.slots.len() - 1;
        let done = |&i: &usize| self.slots[i] == MISS || self.keys[self.slots[i] as usize] == *k;
        let i = ((h >> 32) as usize..).map(|i| i & mask).find(done).unwrap();
        (i, self.slots[i])
    }

    /// The id of `term`, added if new, after adding `role` to its roles.
    fn intern(&mut self, term: &[u8], role: u8) -> u32 {
        let k = key(term, 0, term.len());
        let (i, id) = self.slot(&k);
        if id == MISS {
            self.slots[i] = self.keys.len() as u32;
            self.keys.push(k);
            self.role.push(0);
            self.anchors.push(Vec::new());
        }
        self.role[self.slots[i] as usize] |= role;
        self.slots[i]
    }
}

/// Calls `f` with the term ids (MISS for a token no query uses) of each
/// document in data[lo..hi], which must be whole lines. Pages are released
/// as the scan passes them, so only a few of them stay resident.
fn for_each_doc(data: &[u8], lo: usize, hi: usize, plan: &Plan, mut f: impl FnMut(&[u32])) {
    let (mut i, mut done, mut tokens) = (lo, lo, Vec::new());
    // Bytes that belong to a token (spec 2.2); a table is faster than the test.
    let tok: [bool; 256] = std::array::from_fn(|b| (b as u8).is_ascii_alphanumeric());
    while i < hi {
        i += data[i..].iter().position(|&b| b == b'\t').unwrap() + 1;
        let e = i + data[i..].iter().position(|&b| b == b'\n').unwrap();
        tokenize_words(data, i, e, plan, &tok, &mut tokens);
        i = e;
        i += 1;
        f(&tokens);
        tokens.clear();
        if i - done >= SLICE || i >= hi {
            release(&data[done..i]);
            done = i;
        }
    }
}

// Classify eight independent ASCII lanes, then visit only transitions into
// and out of tokens. Line boundaries are handled before this function.
#[inline]
fn tokenize_words(data: &[u8], start: usize, end: usize, plan: &Plan, tok: &[bool; 256], tokens: &mut Vec<u32>) {
    const H: u64 = 0x8080_8080_8080_8080;
    const LOA: u64 = 0x6161_6161_6161_6161;
    const HIA: u64 = 0x7b7b_7b7b_7b7b_7b7b;
    const LOD: u64 = 0x3030_3030_3030_3030;
    const HID: u64 = 0x3a3a_3a3a_3a3a_3a3a;
    let mut i = start;
    let mut active = false;
    let mut begin = start;
    let mut emit = |p:usize, q:usize| {
        let n=q-p;
        tokens.push(if n <= 32 { plan.slot(&key(data, p, n)).1 } else { MISS });
    };
    while i + 8 <= end {
        let x = u64::from_le_bytes(data[i..i + 8].try_into().unwrap());
        let y = x | 0x2020_2020_2020_2020;
        let a = ((y | H).wrapping_sub(LOA) & !((y | H).wrapping_sub(HIA))) & H;
        let d = ((x | H).wrapping_sub(LOD) & !((x | H).wrapping_sub(HID))) & H;
        let v = (a | d) & !x & H;
        let prior = (v << 8) | if active { 0x80 } else { 0 };
        let opens = v & !prior;
        let closes = !v & prior & H;
        let mut events = opens | closes;
        while events != 0 {
            let bit = events.trailing_zeros() as usize;
            let pos = i + bit / 8;
            if (opens >> bit) & 1 != 0 { begin=pos; } else { emit(begin,pos); }
            events &= events - 1;
        }
        active = v >> 63 != 0;
        i += 8;
    }
    while i < end {
        let v=tok[data[i] as usize];
        if v && !active {begin=i;} else if !v && active {emit(begin,i);}
        active=v;
        i+=1;
    }
    if active {emit(begin,end);}
}

enum Query {
    Bool(Vec<(u8, u32)>), // (first byte of the operator: AND, NOT, else OR; term)
    Phrase(usize),
}

/// Bounded per-chunk phrase matches, deduplicated within each document.
#[derive(Clone)]
struct PhraseStats { count: u32, sum: u64, first: [u32; 10], last: u32 }
impl PhraseStats {
    fn new() -> Self { Self { count: 0, sum: 0, first: [0; 10], last: MISS } }
    fn add(&mut self, doc: u32) {
        if self.last != doc {
            self.last = doc;
            if self.count < 10 { self.first[self.count as usize] = doc; }
            self.count += 1;
            self.sum += u64::from(doc);
        }
    }
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
fn solve_chunk(data: &[u8], lo: usize, hi: usize, plan: &Plan, barrier: &Barrier, bitmap_limit: usize) -> Answers {
    let digits = data[lo..].iter().take_while(|&&b| b != b'\t');
    let first = digits.fold(0, |n, &b| n * 10 + (b - b'0') as u32);
    let nterms = plan.keys.len();
    // Distinct BOOL-term ids of each document, MISS-terminated.
    let mut stream = Vec::with_capacity((hi - lo) / 16);
    let mut last = vec![MISS; nterms];
    let mut hits = vec![PhraseStats::new(); plan.phrases.len()];
    let mut ndocs = 0usize;
    for_each_doc(data, lo, hi, plan, |tokens| {
        let doc = ndocs as u32;
        for (p, &t) in tokens.iter().enumerate().filter(|&(_, &t)| t != MISS) {
            let role = plan.role[t as usize];
            if role & IN_BOOL != 0 && last[t as usize] != doc {
                last[t as usize] = doc;
                stream.push(t);
            }
            if role & ANCHOR == 0 {
                continue;
            }
            for &(q, ph, j) in &plan.anchors[t as usize] {
                if p >= j && tokens.get(p - j..p - j + ph.len()) == Some(ph) {
                    hits[q].add(doc);
                }
            }
        }
        stream.push(MISS);
        ndocs += 1;
    });
    drop(last);
    // Counting sort of the stream into CSR: term t owns docs[offs[t]..offs[t + 1]].
    let mut offs = vec![0u32; nterms + 1];
    for &t in stream.iter().filter(|&&t| t != MISS) {
        offs[t as usize + 1] += 1;
    }
    for t in 0..nterms {
        offs[t + 1] += offs[t];
    }
    let (mut cur, mut docs, mut d) = (offs.clone(), vec![0u32; offs[nterms] as usize], 0);
    for t in stream {
        if t == MISS {
            d += 1;
        } else {
            docs[cur[t as usize] as usize] = d;
            cur[t as usize] += 1;
        }
    }

    // Free the indexing state and wait for every chunk to get here, so the
    // query phase never adds to the memory of a chunk that is still indexing.
    drop(cur);
    barrier.wait();

    // BOOL queries: strictly left-to-right set algebra on the bitmap `r`.
    let words = ndocs.div_ceil(64);
    let (mut r, mut tmp) = (vec![0u64; words], vec![0u64; words]);
    let mut dense = HashMap::new(); // bitmaps of frequent terms, built on first use
    let mut dense_bytes = 0usize;
    let bit = |d: &u32| (*d as usize >> 6, 1u64 << (d & 63));
    let mut top = Vec::new();
    let answer = |qi: usize| {
        let Query::Bool(q) = &plan.queries[qi] else {
            let Query::Phrase(id) = plan.queries[qi] else { unreachable!() };
            let stats = &hits[id];
            let start = top.len() as u32;
            top.extend(stats.first[..(stats.count as usize).min(10)].iter().map(|&d| first + d));
            return (stats.count, start, stats.sum + u64::from(first) * u64::from(stats.count));
        };
        r.fill(0);
        for &(op, t) in q {
            let apply = |x: &mut u64, y: u64| match op {
                b'A' => *x &= y,
                b'N' => *x &= !y,
                _ => *x |= y,
            };
            let post = &docs[offs[t as usize] as usize..offs[t as usize + 1] as usize];
            let bytes = words * std::mem::size_of::<u64>();
            if post.len() * DENSE > ndocs && (dense.contains_key(&t) || bytes <= bitmap_limit.saturating_sub(dense_bytes)) {
                let b = dense.entry(t).or_insert_with(|| {
                    dense_bytes += bytes;
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
        let set_bits = r.iter().enumerate().flat_map(|(w, &x)| {
            let mut x = x;
            std::iter::from_fn(move || {
                let b = x.trailing_zeros();
                x &= x.wrapping_sub(1);
                (b < 64).then_some(w as u32 * 64 + b)
            })
        });
        part(first, set_bits, &mut top)
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
    if len == 0 { return &[]; }
    let fd = std::os::fd::AsRawFd::as_raw_fd(&f);
    // PROT_READ = 1, MAP_PRIVATE = 2 on Linux x86-64 and aarch64.
    let p = unsafe { mmap(std::ptr::null_mut(), len, 1, 2, fd, 0) };
    assert!(p as isize != -1 && !p.is_null(), "mmap failed");
    unsafe { std::slice::from_raw_parts(p, len) }
}

/// Drops the whole pages inside `s` from this process's mapping of the file;
/// the page cache keeps them, so a later read just maps them again.
fn release(s: &[u8]) {
    let lo = (s.as_ptr() as usize).next_multiple_of(4096);
    let hi = (s.as_ptr() as usize + s.len()) & !4095;
    unsafe { madvise(lo as *mut u8, hi.saturating_sub(lo), 4) }; // MADV_DONTNEED
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
    let mut queries = Vec::new();
    let mut phrases = Vec::new();
    let mut unique: HashMap<Vec<u32>, usize> = HashMap::new();
    for line in qtext.split(|&b| b == b'\n').filter(|l| !l.is_empty()) {
        let words: Vec<&[u8]> = line.split(|&b| b == b' ').collect();
        queries.push(if words[0] == b"BOOL" {
            // (operator, term) pairs; the leading "BOOL" acts as OR on the empty set.
            let pair = |w: &[&[u8]]| (w[0][0], plan.intern(w[1], IN_BOOL));
            Query::Bool(words.chunks(2).map(pair).collect())
        } else {
            let terms: Vec<u32> = line[b"PHRASE \"".len()..line.len() - 1].split(|&b| b == b' ').map(|w| plan.intern(w, 0)).collect();
            let id = *unique.entry(terms.clone()).or_insert_with(|| {
                let id = phrases.len();
                phrases.push(terms);
                id
            });
            Query::Phrase(id)
        });
    }
    let data = map_file(&format!("{data_dir}/docs.txt"));

    // Anchor each phrase on its rarest term in a sample of the corpus.
    plan.queries = &queries;
    plan.phrases = &phrases;
    let mut freq = vec![0u32; plan.keys.len()];
    for_each_doc(data, 0, line_start(data, SAMPLE), &plan, |tokens| {
        for &t in tokens.iter().filter(|&&t| t != MISS) {
            freq[t as usize] += 1;
        }
    });
    for (qi, p) in phrases.iter().enumerate() {
        let j = (0..p.len()).min_by_key(|&j| freq[p[j] as usize]).unwrap();
        plan.role[p[j] as usize] |= ANCHOR;
        plan.anchors[p[j] as usize].push((qi, &p[..], j));
    }

    // Equal byte ranges, each moved to just after an LF.
    let cut = |k| line_start(data, k * data.len() / nthreads);
    let barrier = Barrier::new(nthreads);
    let bitmap_limit = 64 * 1024 * 1024 / nthreads;
    let parts: Vec<Answers> = thread::scope(|s| {
        let (plan, barrier) = (&plan, &barrier);
        let hs: Vec<_> = (0..nthreads)
            .map(|k| s.spawn(move || solve_chunk(data, cut(k), cut(k + 1), plan, barrier, bitmap_limit)))
            .collect();
        hs.into_iter().map(|h| h.join().unwrap()).collect()
    });
    let mut out = String::new();
    for qi in 0..queries.len() {
        let n: u32 = parts.iter().map(|(c, _)| c[qi].0).sum();
        let sum: u64 = parts.iter().map(|(c, _)| c[qi].2).sum();
        write!(out, "{n} {sum}").unwrap();
        let top = parts.iter().flat_map(|(c, ids)| &ids[c[qi].1 as usize..][..c[qi].0.min(10) as usize]);
        for d in top.take(10) {
            write!(out, " {d}").unwrap();
        }
        out.push('\n');
    }
    fs::create_dir_all(&out_dir).ok();
    fs::write(format!("{out_dir}/results.txt"), out).expect("write results.txt");
}

#[cfg(test)] mod swar_review {
use super::*;
fn check(data:&[u8],start:usize,end:usize,plan:&Plan,tok:&[bool;256]) {
  let mut actual=Vec::new(); tokenize_words(data,start,end,plan,tok,&mut actual);
  let mut exp=Vec::new(); let mut i=start;
  while i<end {
    while i<end && !tok[data[i] as usize] {i+=1;}
    let begin=i;while i<end && tok[data[i] as usize] {i+=1;}
    if i>begin {let n=i-begin;exp.push(if n<=32 {plan.slot(&key(data,begin,n)).1} else {MISS});}
  }
  assert_eq!(actual,exp,"start={start} end={end} bytes={:?}",&data[start..end]);
}
#[test] fn byte_lanes_and_transitions(){
 let tok:[bool;256]=std::array::from_fn(|i| (i as u8).is_ascii_alphanumeric());
 let mut plan=Plan { slots:vec![MISS;1024], ..Default::default() };
 for x in b'a'..=b'z' {plan.intern(&[x],0);} for x in b'0'..=b'9' {plan.intern(&[x],0);}
 for n in 1..=32 {plan.intern(&vec![b'a';n],0);}
 for prefix in 0..16 {for len in 0..=48 {for position in 0..len {for byte in 0u16..=255 {
   let mut v=vec![b'a';prefix+len+32];v[prefix+position]=byte as u8;check(&v,prefix,prefix+len,&plan,&tok);
 }}}}
 for mask in 0..(1u32<<16) {let mut v=vec![b'-';48];for j in 0..16 {if mask&(1<<j)!=0 {v[13+j]=b'a';}}
   check(&v,13,29,&plan,&tok);
 }
 let mut z=0x9e3779b97f4a7c15u64;
 for case in 0..100_000 {z^=z<<13;z^=z>>7;z^=z<<17;let len=(z as usize)%129;let prefix=(z as usize>>9)%16;let mut v=vec![0u8;prefix+len+32];for x in &mut v {z^=z<<13;z^=z>>7;z^=z<<17;*x=z as u8;};check(&v,prefix,prefix+len,&plan,&tok);if case%10000==0 {eprintln!("random {case}");}}
}
}
