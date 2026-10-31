//! Speed Demon 2026, Track B (Index). Standard library only.
//!
//! 1. Parse the queries first and intern every term they use. Each phrase is
//!    anchored on its rarest term, judged from a small sample of the corpus.
//! 2. Map docs.txt and tokenize it once on all cores. BOOL terms get posting
//!    lists; phrases are checked right there, around each anchor occurrence.
//! 3. Answer BOOL queries on all cores with a dense bitmap of all documents.

use std::fmt::Write as _;
use std::sync::OnceLock;
use std::{env, fs, thread};

/// Term id of a token that no query uses.
const MISS: u32 = u32::MAX;
/// Pseudo term id passed after the last token of each document.
const END: u32 = u32::MAX - 1;
/// A term with df > N / DENSE is used as a bitmap rather than a list.
const DENSE: usize = 32;
/// Bytes of corpus read up front to estimate which phrase term is rarest.
const SAMPLE: usize = 1 << 19;
/// Bytes of corpus a thread scans between releasing what it has read.
const SLICE: usize = 1 << 22;

/// Lowercased token byte, or 0 for a separator (spec 2.2).
const LOW: [u8; 256] = {
    let mut t = [0u8; 256];
    let mut i = 0;
    while i < 256 {
        t[i] = match i as u8 {
            b'a'..=b'z' | b'0'..=b'9' => i as u8,
            b'A'..=b'Z' => i as u8 + 32,
            _ => 0,
        };
        i += 1;
    }
    t
};

/// A token packed into 32 bytes, zero-padded; tokens never contain a zero byte.
#[derive(Clone, Copy, PartialEq, Eq)]
#[repr(align(32))]
struct Key([u64; 4]);

impl Key {
    /// Packs the n-byte token at data[s..]. Token bytes are ASCII letters and
    /// digits, so OR-ing 0x20 lowercases letters and leaves digits alone.
    fn new(data: &[u8], s: usize, n: usize) -> Key {
        let mut pad = [0u8; 32];
        let src = match data.get(s..s + 32) {
            Some(src) => src,
            None => {
                pad[..n].copy_from_slice(&data[s..s + n]);
                &pad
            }
        };
        let mut k = [0u64; 4];
        for (w, kw) in k.iter_mut().enumerate() {
            let x = u64::from_le_bytes(src[w * 8..w * 8 + 8].try_into().unwrap());
            let valid = n.saturating_sub(w * 8).min(8);
            let mask = ((1u128 << (valid * 8)) - 1) as u64;
            *kw = (x | 0x2020_2020_2020_2020) & mask;
        }
        Key(k)
    }
}

/// Open-addressing table from query term to dense id.
struct Dict {
    slots: Vec<u32>,
    keys: Vec<Key>,
}

impl Dict {
    fn slot(&self, k: &Key) -> (usize, u32) {
        let [a, b, c, d] = k.0;
        let h = (a ^ b.rotate_left(17) ^ c.rotate_left(31) ^ d.rotate_left(47))
            .wrapping_mul(0x9e37_79b9_7f4a_7c15);
        let mask = self.slots.len() - 1;
        let mut i = (h >> 32) as usize & mask;
        loop {
            let id = self.slots[i];
            if id == MISS || self.keys[id as usize] == *k {
                return (i, id);
            }
            i = (i + 1) & mask;
        }
    }

    fn intern(&mut self, term: &[u8]) -> u32 {
        let (i, id) = self.slot(&Key::new(term, 0, term.len()));
        if id != MISS {
            return id;
        }
        self.slots[i] = self.keys.len() as u32;
        self.keys.push(Key::new(term, 0, term.len()));
        self.slots[i]
    }
}

/// Calls `f` with the term id (or MISS) of every token of the documents in
/// data[lo..hi], which must be whole lines, and with END after each document.
fn for_each_token(data: &[u8], lo: usize, hi: usize, dict: &Dict, mut f: impl FnMut(u32)) {
    let mut i = lo;
    while i < hi {
        while data[i] != b'\t' {
            i += 1;
        }
        i += 1;
        loop {
            let c = data[i];
            if LOW[c as usize] != 0 {
                let s = i;
                while LOW[data[i] as usize] != 0 {
                    i += 1;
                }
                f(if i - s <= 32 {
                    dict.slot(&Key::new(data, s, i - s)).1
                } else {
                    MISS
                });
            } else {
                i += 1;
                if c == b'\n' {
                    break;
                }
            }
        }
        f(END);
    }
}

enum Query {
    Bool(Vec<(u8, u32)>), // (operator b'A' / b'O' / b'N', term); the first op is b'O'
    Phrase(Vec<u32>),
}

fn parse_queries(text: &[u8], dict: &mut Dict) -> Vec<Query> {
    let mut qs = Vec::new();
    for line in text.split(|&b| b == b'\n').filter(|l| !l.is_empty()) {
        if let Some(rest) = line.strip_prefix(b"BOOL ") {
            let mut op = b'O';
            let mut q = Vec::new();
            for (i, w) in rest.split(|&b| b == b' ').enumerate() {
                if i % 2 == 1 {
                    op = w[0];
                } else {
                    q.push((op, dict.intern(w)));
                }
            }
            qs.push(Query::Bool(q));
        } else {
            let rest = &line[b"PHRASE \"".len()..line.len() - 1];
            qs.push(Query::Phrase(
                rest.split(|&b| b == b' ').map(|w| dict.intern(w)).collect(),
            ));
        }
    }
    qs
}

/// What the corpus scan has to do for each term.
struct Plan<'q> {
    queries: &'q [Query],
    in_bool: Vec<bool>,
    anchor_offs: Vec<u32>, // term t anchors anchors[anchor_offs[t]..anchor_offs[t + 1]]
    anchors: Vec<(u32, usize)>, // (query index, position of the anchor term in the phrase)
}

impl<'q> Plan<'q> {
    fn new(queries: &'q [Query], nterms: usize, sample_count: &[u32]) -> Self {
        let mut in_bool = vec![false; nterms];
        let mut by_term = vec![Vec::new(); nterms];
        for (qi, q) in queries.iter().enumerate() {
            match q {
                Query::Bool(q) => q.iter().for_each(|&(_, t)| in_bool[t as usize] = true),
                Query::Phrase(p) => {
                    let j = (0..p.len())
                        .min_by_key(|&j| sample_count[p[j] as usize])
                        .unwrap();
                    by_term[p[j] as usize].push((qi as u32, j));
                }
            }
        }
        let mut anchor_offs = vec![0];
        anchor_offs.extend(by_term.iter().scan(0, |n, v| {
            *n += v.len() as u32;
            Some(*n)
        }));
        Plan {
            queries,
            in_bool,
            anchor_offs,
            anchors: by_term.concat(),
        }
    }

    fn anchored(&self, t: u32) -> &[(u32, usize)] {
        &self.anchors
            [self.anchor_offs[t as usize] as usize..self.anchor_offs[t as usize + 1] as usize]
    }
}

/// BOOL posting lists of one chunk in CSR form (term t owns docs[offs[t]..offs[t + 1]]),
/// plus the (query, doc) pairs of every phrase match in the chunk.
struct Chunk {
    ndocs: u32,
    offs: Vec<u32>,
    docs: Vec<u32>,
    matches: Vec<(u32, u32)>,
}

impl Chunk {
    fn list(&self, t: u32) -> &[u32] {
        &self.docs[self.offs[t as usize] as usize..self.offs[t as usize + 1] as usize]
    }
}

/// Indexes the whole lines in data[lo..hi].
fn index_chunk(data: &[u8], lo: usize, hi: usize, dict: &Dict, plan: &Plan) -> Chunk {
    let first = data[lo..]
        .iter()
        .take_while(|&&b| b != b'\t')
        .fold(0, |n, &b| n * 10 + (b - b'0') as u32);
    let nterms = dict.keys.len();
    // Distinct BOOL-term ids of each document, MISS-terminated.
    let mut stream = Vec::with_capacity((hi - lo) / 16);
    let mut last = vec![MISS; nterms];
    let (mut tokens, mut hits, mut matches) = (Vec::new(), Vec::new(), Vec::new());
    let mut doc = first;
    let mut on_token = |t| {
        if t == END {
            let doc_matches = matches.len();
            for &p in &hits {
                for &(q, j) in plan.anchored(tokens[p]) {
                    let Query::Phrase(ph) = &plan.queries[q as usize] else {
                        unreachable!()
                    };
                    let ok = p >= j && tokens.get(p - j..p - j + ph.len()) == Some(&ph[..]);
                    if ok && !matches[doc_matches..].contains(&(q, doc)) {
                        matches.push((q, doc));
                    }
                }
            }
            tokens.clear();
            hits.clear();
            stream.push(MISS);
            doc += 1;
            return;
        }
        if t != MISS {
            if plan.in_bool[t as usize] && last[t as usize] != doc {
                last[t as usize] = doc;
                stream.push(t);
            }
            if plan.anchor_offs[t as usize] != plan.anchor_offs[t as usize + 1] {
                hits.push(tokens.len());
            }
        }
        tokens.push(t);
    };
    // Scan in slices, dropping each scanned slice from our page tables so
    // resident memory holds only a few pages of the corpus at a time.
    let mut i = lo;
    while i < hi {
        let end = line_end(data, i + SLICE).min(hi);
        for_each_token(data, i, end, dict, &mut on_token);
        release(&data[i..end]);
        i = end;
    }
    // Counting sort of the stream into CSR.
    let mut offs = vec![0u32; nterms + 1];
    stream
        .iter()
        .filter(|&&t| t != MISS)
        .for_each(|&t| offs[t as usize + 1] += 1);
    for t in 0..nterms {
        offs[t + 1] += offs[t];
    }
    let mut cur = offs.clone();
    let mut docs = vec![0u32; offs[nterms] as usize];
    let mut d = first;
    for &t in &stream {
        if t == MISS {
            d += 1;
        } else {
            docs[cur[t as usize] as usize] = d;
            cur[t as usize] += 1;
        }
    }
    Chunk {
        ndocs: doc - first,
        offs,
        docs,
        matches,
    }
}

/// Posting lists of all chunks, in doc order.
struct Index {
    chunks: Vec<Chunk>,
    ndocs: usize,
    dense: Vec<OnceLock<Vec<u64>>>, // bitmap of a frequent term, built on first use
}

impl Index {
    fn post(&self, t: u32) -> impl Iterator<Item = u32> + '_ {
        self.chunks
            .iter()
            .flat_map(move |c| c.list(t).iter().copied())
    }

    /// The term as a bitmap over all documents, if it is frequent enough to pay off.
    fn bitmap(&self, t: u32) -> Option<&[u64]> {
        let df: usize = self.chunks.iter().map(|c| c.list(t).len()).sum();
        (df * DENSE > self.ndocs).then(|| {
            &self.dense[t as usize].get_or_init(|| {
                let mut b = vec![0u64; self.ndocs.div_ceil(64)];
                self.post(t)
                    .for_each(|d| b[d as usize >> 6] |= 1 << (d & 63));
                b
            })[..]
        })
    }

    /// Strictly left-to-right set algebra on the bitmap `r`; returns the ids in `r`.
    fn run_bool(&self, q: &[(u8, u32)], r: &mut Vec<u64>, tmp: &mut Vec<u64>) -> Vec<u32> {
        r.fill(0);
        for &(op, t) in q {
            if let Some(b) = self.bitmap(t) {
                let f: fn(&mut u64, u64) = match op {
                    b'O' => |x, y| *x |= y,
                    b'N' => |x, y| *x &= !y,
                    _ => |x, y| *x &= y,
                };
                r.iter_mut().zip(b).for_each(|(x, &y)| f(x, y));
                continue;
            }
            let bit = |d: u32| (d as usize >> 6, 1u64 << (d & 63));
            match op {
                b'O' => self.post(t).map(bit).for_each(|(w, m)| r[w] |= m),
                b'N' => self.post(t).map(bit).for_each(|(w, m)| r[w] &= !m),
                _ => {
                    tmp.fill(0);
                    self.post(t).map(bit).for_each(|(w, m)| tmp[w] |= r[w] & m);
                    std::mem::swap(r, tmp);
                }
            }
        }
        let mut out = Vec::new();
        for (w, &x) in r.iter().enumerate() {
            let mut x = x;
            while x != 0 {
                out.push((w * 64) as u32 + x.trailing_zeros());
                x &= x - 1;
            }
        }
        out
    }
}

/// Maps a read-only file into memory (std has no mmap; libc is always linked).
fn map_file(path: &str) -> &'static [u8] {
    extern "C" {
        fn mmap(addr: *mut u8, len: usize, prot: i32, flags: i32, fd: i32, off: i64) -> *mut u8;
    }
    use std::os::fd::AsRawFd;
    let f = fs::File::open(path).expect("open docs.txt");
    let len = f.metadata().unwrap().len() as usize;
    if len == 0 {
        return &[];
    }
    // PROT_READ = 1, MAP_PRIVATE = 2 on Linux x86-64 and aarch64.
    let p = unsafe { mmap(std::ptr::null_mut(), len, 1, 2, f.as_raw_fd(), 0) };
    assert!(p as isize != -1, "mmap failed");
    unsafe { std::slice::from_raw_parts(p, len) }
}

/// Drops the whole pages inside `s` from this process's mapping of the file;
/// the page cache keeps them, so a later read just maps them again.
fn release(s: &[u8]) {
    extern "C" {
        fn madvise(addr: *mut u8, len: usize, advice: i32) -> i32;
    }
    let lo = (s.as_ptr() as usize).next_multiple_of(4096);
    let hi = (s.as_ptr() as usize + s.len()) & !4095;
    if hi > lo {
        unsafe { madvise(lo as *mut u8, hi - lo, 4) }; // MADV_DONTNEED
    }
}

/// The index just past the first LF at or after `i`.
fn line_end(data: &[u8], i: usize) -> usize {
    data[i.min(data.len())..]
        .iter()
        .position(|&b| b == b'\n')
        .map_or(data.len(), |p| i + p + 1)
}

fn main() {
    let data_dir = env::var("SD_DATA").unwrap_or_else(|_| "/data".into());
    let out_dir = env::var("SD_OUT").unwrap_or_else(|_| "/out".into());
    let nthreads = thread::available_parallelism().map_or(4, |n| n.get());

    let qtext = fs::read(format!("{data_dir}/queries.txt")).expect("read queries.txt");
    let nwords = qtext.iter().filter(|&&b| b == b' ').count();
    let mut dict = Dict {
        slots: vec![MISS; (2 * nwords).next_power_of_two().max(1024)],
        keys: Vec::new(),
    };
    let queries = parse_queries(&qtext, &mut dict);
    let data = map_file(&format!("{data_dir}/docs.txt"));

    let mut sample_count = vec![0u32; dict.keys.len()];
    let sample_end = if data.is_empty() {
        0
    } else {
        line_end(data, SAMPLE.min(data.len()) - 1)
    };
    for_each_token(data, 0, sample_end, &dict, |t| {
        if t < END {
            sample_count[t as usize] += 1;
        }
    });
    let plan = Plan::new(&queries, dict.keys.len(), &sample_count);

    // Equal byte ranges, each moved to just after an LF.
    let mut cuts: Vec<usize> = (0..nthreads)
        .map(|k| {
            if k == 0 {
                0
            } else {
                line_end(data, k * data.len() / nthreads - 1)
            }
        })
        .collect();
    cuts.push(data.len());
    cuts.dedup();
    let chunks: Vec<Chunk> = thread::scope(|s| {
        let hs: Vec<_> = cuts
            .windows(2)
            .map(|w| s.spawn(|| index_chunk(data, w[0], w[1], &dict, &plan)))
            .collect();
        hs.into_iter().map(|h| h.join().unwrap()).collect()
    });
    let mut phrase_hits = vec![Vec::new(); queries.len()];
    chunks
        .iter()
        .flat_map(|c| &c.matches)
        .for_each(|&(q, d)| phrase_hits[q as usize].push(d));
    let ndocs = chunks.iter().map(|c| c.ndocs as usize).sum();
    let idx = Index {
        chunks,
        ndocs,
        dense: (0..dict.keys.len()).map(|_| OnceLock::new()).collect(),
    };

    // Answer queries in a few blocks per thread; each block becomes one string.
    let words = ndocs.div_ceil(64);
    let outs: Vec<String> = thread::scope(|s| {
        let block = queries.len().div_ceil(nthreads * 4).max(1);
        let hs: Vec<_> = (0..queries.len())
            .step_by(block)
            .map(|lo| {
                let (idx, queries, phrase_hits) = (&idx, &queries, &phrase_hits);
                s.spawn(move || {
                    let (mut r, mut tmp, mut out) = (vec![0; words], vec![0; words], String::new());
                    for qi in lo..(lo + block).min(queries.len()) {
                        let bool_ids;
                        let ids = match &queries[qi] {
                            Query::Bool(q) => {
                                bool_ids = idx.run_bool(q, &mut r, &mut tmp);
                                &bool_ids
                            }
                            Query::Phrase(_) => &phrase_hits[qi],
                        };
                        let sum: u64 = ids.iter().map(|&d| d as u64).sum();
                        write!(out, "{} {}", ids.len(), sum).unwrap();
                        ids.iter()
                            .take(10)
                            .for_each(|d| write!(out, " {d}").unwrap());
                        out.push('\n');
                    }
                    out
                })
            })
            .collect();
        hs.into_iter().map(|h| h.join().unwrap()).collect()
    });
    let out = outs.concat();
    fs::create_dir_all(&out_dir).ok();
    fs::write(format!("{out_dir}/results.txt"), out).expect("write results.txt");
}
