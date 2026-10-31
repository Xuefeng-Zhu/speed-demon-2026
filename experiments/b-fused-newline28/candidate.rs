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
use std::{collections::HashMap, env, fs, thread, sync::{OnceLock, atomic::{AtomicUsize, Ordering}}};

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
    short_slots: Vec<u32>,
}

impl Plan<'_> {
    #[inline]
    fn short_hash(mut x: u64) -> usize {
        x ^= x >> 30;
        x = x.wrapping_mul(0xbf58_476d_1ce4_e5b9);
        x ^= x >> 27;
        x = x.wrapping_mul(0x94d0_49bb_1331_11eb);
        ((x ^ (x >> 31)) >> 32) as usize
    }

    fn build_short(&mut self) {
        let count = self.keys.iter().filter(|k| k.0[1..].iter().all(|&x| x == 0)).count();
        self.short_slots = vec![MISS; (count * 2).max(1).next_power_of_two()];
        let mask = self.short_slots.len() - 1;
        for (id, k) in self.keys.iter().enumerate() {
            if k.0[1..].iter().any(|&x| x != 0) { continue; }
            let mut i = Self::short_hash(k.0[0]) & mask;
            while self.short_slots[i] != MISS { i = (i + 1) & mask; }
            self.short_slots[i] = id as u32;
        }
    }

    #[inline]
    fn lookup_token(&self, data: &[u8], p: usize, n: usize) -> u32 {
        if n > 8 { return self.slot(&key(data, p, n)).1; }
        let mut pad = [0u8; 8];
        let src = data.get(p..p+8).unwrap_or_else(|| {pad[..n].copy_from_slice(&data[p..p+n]); &pad});
        let x = u64::from_le_bytes(src.try_into().unwrap()) | 0x2020_2020_2020_2020;
        let x = x & ((1u128 << (n * 8)) - 1) as u64;
        let mask = self.short_slots.len() - 1;
        let mut i = Self::short_hash(x) & mask;
        loop {
            let id = self.short_slots[i];
            if id == MISS || self.keys[id as usize].0[0] == x { return id; }
            i = (i + 1) & mask;
        }
    }
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
// Each vector load is guarded by the remaining bytes in the whole-line chunk.
#[inline]
unsafe fn classify_scalar(p: *const u8) -> u64 {
    let (mut tokens, mut newlines) = (0u32, 0u32);
    for j in 0..32 {
        let c = unsafe { *p.add(j) };
        tokens |= u32::from(c.is_ascii_alphanumeric()) << j;
        newlines |= u32::from(c == b'\n') << j;
    }
    u64::from(tokens) | (u64::from(newlines) << 32)
}

#[cfg(target_arch = "x86_64")]
#[target_feature(enable = "avx2")]
unsafe fn classify_avx2(p: *const u8) -> u64 {
    use std::arch::x86_64::*;
    let v = _mm256_loadu_si256(p.cast());
    let low = _mm256_or_si256(v, _mm256_set1_epi8(0x20));
    let alpha = _mm256_and_si256(_mm256_cmpgt_epi8(low, _mm256_set1_epi8(b'a' as i8 - 1)),
                                 _mm256_cmpgt_epi8(_mm256_set1_epi8(b'z' as i8 + 1), low));
    let digit = _mm256_and_si256(_mm256_cmpgt_epi8(v, _mm256_set1_epi8(b'0' as i8 - 1)),
                                 _mm256_cmpgt_epi8(_mm256_set1_epi8(b'9' as i8 + 1), v));
    let words = _mm256_movemask_epi8(_mm256_or_si256(alpha, digit)) as u32;
    let lines = _mm256_movemask_epi8(_mm256_cmpeq_epi8(v, _mm256_set1_epi8(b'\n' as i8))) as u32;
    u64::from(words) | (u64::from(lines) << 32)
}

#[inline]
fn push_word(data: &[u8], start: usize, end: usize, plan: &Plan, tokens: &mut Vec<u32>) {
    let n = end - start;
    tokens.push(if n <= 32 { plan.lookup_token(data, start, n) } else { MISS });
}

fn for_each_doc(data: &[u8], lo: usize, hi: usize, plan: &Plan, mut f: impl FnMut(&[u32])) {
    let (mut i, mut done, mut tokens) = (lo, lo, Vec::new());
    let classify: unsafe fn(*const u8) -> u64 = {
        #[cfg(target_arch = "x86_64")]
        { if std::is_x86_feature_detected!("avx2") { classify_avx2 } else { classify_scalar } }
        #[cfg(not(target_arch = "x86_64"))]
        { classify_scalar }
    };
    while i < hi {
        i += data[i..hi].iter().position(|&b| b == b'\t').unwrap() + 1;
        let mut pos = i;
        let mut open = None;
        let mut ended = false;
        while hi - pos >= 32 {
            let masks = unsafe { classify(data.as_ptr().add(pos)) };
            let newline = (masks >> 32) as u32;
            let span = if newline == 0 { 32 } else { newline.trailing_zeros() as usize };
            let valid = if span == 32 { u32::MAX } else if span == 0 { 0 } else { u32::MAX >> (32 - span) };
            let mask = masks as u32 & valid;
            let mut pending = mask;
            if let Some(start) = open.take() {
                let k = (mask.trailing_ones() as usize).min(span);
                if k == span { open = Some(start); }
                else {
                    push_word(data, start, pos + k, plan, &mut tokens);
                    pending &= u32::MAX << k;
                }
            }
            if open.is_none() {
                while pending != 0 {
                    let start = pending.trailing_zeros() as usize;
                    let len = (pending >> start).trailing_ones() as usize;
                    let stop = start + len;
                    if stop == span { open = Some(pos + start); break; }
                    push_word(data, pos + start, pos + stop, plan, &mut tokens);
                    pending &= u32::MAX << stop;
                }
            }
            pos += span;
            if newline != 0 {
                if let Some(start) = open.take() { push_word(data, start, pos, plan, &mut tokens); }
                i = pos + 1;
                ended = true;
                break;
            }
        }
        if !ended {
            while pos < hi && data[pos] != b'\n' {
                if data[pos].is_ascii_alphanumeric() {
                    if open.is_none() { open = Some(pos); }
                } else if let Some(start) = open.take() {
                    push_word(data, start, pos, plan, &mut tokens);
                }
                pos += 1;
            }
            assert!(pos < hi, "unterminated input line");
            if let Some(start) = open { push_word(data, start, pos, plan, &mut tokens); }
            i = pos + 1;
        }
        f(&tokens);
        tokens.clear();
        if i - done >= SLICE || i >= hi {
            release(&data[done..i]);
            done = i;
        }
    }
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

/// Exact per-chunk postings and bounded phrase summaries.
struct ChunkIndex { first: u32, ndocs: usize, offs: Vec<u32>, docs: Vec<u32>, hits: Vec<PhraseStats> }
fn index_chunk(data: &[u8], lo: usize, hi: usize, plan: &Plan) -> ChunkIndex {
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

    ChunkIndex { first, ndocs, offs, docs, hits }
}

/// Shared global dense bitmaps are built once per term under a total payload cap.
struct DenseCache { slots: Vec<OnceLock<Option<Box<[u64]>>>>, used: AtomicUsize, limit: usize }
impl DenseCache {
    fn new(nterms: usize, limit: usize) -> Self {
        Self { slots: (0..nterms).map(|_| OnceLock::new()).collect(), used: AtomicUsize::new(0), limit }
    }
    fn get(&self, term: usize, parts: &[ChunkIndex], words: usize) -> Option<&[u64]> {
        self.slots[term].get_or_init(|| {
            let bytes = words * std::mem::size_of::<u64>();
            if self.used.fetch_update(Ordering::Relaxed, Ordering::Relaxed,
                |used| used.checked_add(bytes).filter(|&end| end <= self.limit)).is_err() { return None; }
            let mut bitmap = vec![0u64; words];
            for p in parts {
                for &d in &p.docs[p.offs[term] as usize..p.offs[term + 1] as usize] {
                    let doc = p.first + d;
                    bitmap[doc as usize >> 6] |= 1u64 << (doc & 63);
                }
            }
            Some(bitmap.into_boxed_slice())
        }).as_deref()
    }
}

/// Answer one contiguous query range over all disjoint chunks.
fn answer_range(parts: &[ChunkIndex], plan: &Plan, lo: usize, hi: usize, freqs: &[u32], cache: &DenseCache) -> Answers {
    let ndocs: usize = parts.iter().map(|part| part.ndocs).sum();
    // BOOL queries: strictly left-to-right set algebra on the bitmap `r`.
    let words = ndocs.div_ceil(64);
    let (mut r, mut tmp) = (vec![0u64; words], vec![0u64; words]);
    let bit = |d: u32| (d as usize >> 6, 1u64 << (d & 63));
    let mut top = Vec::new();
    let answer = |qi: usize| {
        let Query::Bool(q) = &plan.queries[qi] else {
            let Query::Phrase(id) = plan.queries[qi] else { unreachable!() };
            let start = top.len() as u32;
            let (mut count, mut sum) = (0u32, 0u64);
            for part in parts {
                let stats = &part.hits[id];
                count += stats.count;
                sum += stats.sum + u64::from(part.first) * u64::from(stats.count);
                let remaining = 10usize.saturating_sub(top.len() - start as usize);
                top.extend(stats.first[..(stats.count as usize).min(remaining)].iter().map(|&d| part.first + d));
            }
            return (count, start, sum);
        };
        r.fill(0);
        for &(op, t) in q {
            let apply = |x: &mut u64, y: u64| match op {
                b'A' => *x &= y,
                b'N' => *x &= !y,
                _ => *x |= y,
            };
            let postlen = freqs[t as usize] as usize;
            let visit = |f: &mut dyn FnMut(usize, u64)| {
                for part in parts {
                    for &d in &part.docs[part.offs[t as usize] as usize..part.offs[t as usize + 1] as usize] {
                        let (w,m) = bit(part.first + d); f(w,m);
                    }
                }
            };
            if postlen * DENSE > ndocs {
                if let Some(b) = cache.get(t as usize, parts, words) {
                    r.iter_mut().zip(b).for_each(|(x, &y)| apply(x, y));
                    continue;
                }
            }
            if op == b'A' {
                tmp.fill(0);
                visit(&mut |w,m| tmp[w] |= r[w] & m);
                std::mem::swap(&mut r, &mut tmp);
            } else {
                visit(&mut |w,m| apply(&mut r[w], m));
            }
        }
        let start = top.len() as u32;
        let (mut count, mut sum) = (0u32, 0u64);
        for (w, &word) in r.iter().enumerate() {
            if word == 0 { continue; }
            let n = word.count_ones();
            let base = w as u32 * 64;
            count += n;
            sum += u64::from(base) * u64::from(n);
            let mut bits = word;
            if n <= 8 {
                while bits != 0 {
                    let pos = bits.trailing_zeros();
                    sum += u64::from(pos);
                    if top.len() - (start as usize) < 10 { top.push(base + pos); }
                    bits &= bits - 1;
                }
            } else {
                sum += u64::from((word & 0xaaaaaaaaaaaaaaaa).count_ones());
                sum += u64::from((word & 0xcccccccccccccccc).count_ones()) * 2;
                sum += u64::from((word & 0xf0f0f0f0f0f0f0f0).count_ones()) * 4;
                sum += u64::from((word & 0xff00ff00ff00ff00).count_ones()) * 8;
                sum += u64::from((word & 0xffff0000ffff0000).count_ones()) * 16;
                sum += u64::from((word & 0xffffffff00000000).count_ones()) * 32;
                while bits != 0 && top.len() - (start as usize) < 10 {
                    let pos = bits.trailing_zeros();
                    top.push(base + pos);
                    bits &= bits - 1;
                }
            }
        }
        (count, start, sum)
    };
    let counts = (lo..hi).map(answer).collect();
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
    plan.build_short();
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
    let parts: Vec<ChunkIndex> = thread::scope(|s| {
        let plan = &plan;
        let hs: Vec<_> = (0..nthreads)
            .map(|k| s.spawn(move || index_chunk(data, cut(k), cut(k + 1), plan)))
            .collect();
        hs.into_iter().map(|h| h.join().unwrap()).collect()
    });
    let mut freqs = vec![0u32; plan.keys.len()];
    for part in &parts {
        for (t, f) in freqs.iter_mut().enumerate() { *f += part.offs[t + 1] - part.offs[t]; }
    }
    let cache = DenseCache::new(plan.keys.len(), 64 * 1024 * 1024);
    const QUERY_BLOCK: usize = 256;
    let next = AtomicUsize::new(0);
    let mut answers: Vec<(usize, Answers)> = thread::scope(|s| {
        let (plan, parts, cache, freqs, next) = (&plan, &parts, &cache, &freqs, &next);
        let hs: Vec<_> = (0..nthreads).map(|_| s.spawn(move || {
            let mut owned = Vec::new();
            loop {
                let lo = next.fetch_add(QUERY_BLOCK, Ordering::Relaxed);
                if lo >= plan.queries.len() { break; }
                let hi = lo.saturating_add(QUERY_BLOCK).min(plan.queries.len());
                owned.push((lo, answer_range(parts, plan, lo, hi, freqs, cache)));
            }
            owned
        })).collect();
        hs.into_iter().flat_map(|h| h.join().unwrap()).collect()
    });
    answers.sort_unstable_by_key(|(lo, _)| *lo);
    let mut out = String::new();
    for (_, (counts, ids)) in &answers {
        for &(n, start, sum) in counts {
            write!(out, "{n} {sum}").unwrap();
            for d in &ids[start as usize..start as usize + n.min(10) as usize] { write!(out, " {d}").unwrap(); }
            out.push('\n');
        }
    }
    fs::create_dir_all(&out_dir).ok();
    fs::write(format!("{out_dir}/results.txt"), out).expect("write results.txt");
}
