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

// PROF: profiling helpers (experiments/b-linux-profile). Everything marked PROF is
// instrumentation only; the output logic is that of baseline.rs. All lines go to
// stderr at the end of the run, so nothing is printed while a phase runs.
static T0: std::sync::OnceLock<std::time::Instant> = std::sync::OnceLock::new();

/// PROF: nanoseconds since the start of main.
fn ns() -> u64 {
    T0.get().unwrap().elapsed().as_nanos() as u64
}

/// PROF: kB values of the named fields of a /proc/self file, 0 when absent.
fn proc_kb(path: &str, names: &[&str]) -> Vec<u64> {
    let s = fs::read_to_string(path).unwrap_or_default();
    names
        .iter()
        .map(|n| {
            s.lines()
                .find(|l| l.starts_with(n) && l[n.len()..].starts_with(':'))
                .and_then(|l| l[n.len() + 1..].split_whitespace().next()?.parse().ok())
                .unwrap_or(0)
        })
        .collect()
}

/// PROF: `MEM <phase> <VmHWM> <VmRSS> <RssAnon> <RssFile>` in kB.
fn mem_line(log: &mut String, name: &str) {
    let v = proc_kb("/proc/self/status", &["VmHWM", "VmRSS", "RssAnon", "RssFile"]);
    writeln!(log, "MEM {name} {} {} {} {}", v[0], v[1], v[2], v[3]).unwrap();
}

/// PROF: end of a phase: `PHASE <name> <ns since start>` (taken before reading
/// memory, so the read is charged to the next phase), then its MEM line, and
/// with SD_PROF_SMAPS=1 at the chosen boundaries
/// `SMAPS <phase> <Rss> <Pss> <Pss_Anon> <Pss_File> <Anonymous>` from smaps_rollup.
fn phase(log: &mut String, name: &str) {
    let t = ns();
    writeln!(log, "PHASE {name} {t}").unwrap();
    mem_line(log, name);
    if env::var_os("SD_PROF_SMAPS").is_some() && matches!(name, "rows_alloc" | "index" | "answer" | "write") {
        let v = proc_kb("/proc/self/smaps_rollup", &["Rss", "Pss", "Pss_Anon", "Pss_File", "Anonymous"]);
        writeln!(log, "SMAPS {name} {} {} {} {} {}", v[0], v[1], v[2], v[3], v[4]).unwrap();
    }
}

static SAMPLER_STOP: std::sync::atomic::AtomicBool = std::sync::atomic::AtomicBool::new(false);

/// PROF: with SD_PROF_SAMPLE_US=n, a thread that reads /proc/self/status every
/// n microseconds and returns `MEMT <ns> <VmRSS> <RssAnon> <RssFile>` lines.
fn sampler() -> Option<thread::JoinHandle<String>> {
    let us: u64 = env::var("SD_PROF_SAMPLE_US").ok()?.parse().ok()?;
    Some(thread::spawn(move || {
        let mut log = String::new();
        while !SAMPLER_STOP.load(Relaxed) {
            let t = ns();
            let v = proc_kb("/proc/self/status", &["VmRSS", "RssAnon", "RssFile"]);
            writeln!(log, "MEMT {t} {} {} {}", v[0], v[1], v[2]).unwrap();
            thread::sleep(std::time::Duration::from_micros(us));
        }
        log
    }))
}

/// Bytes of corpus read up front to estimate which phrase term is rarest.
const SAMPLE: usize = 1 << 19;
/// Bytes of corpus a thread scans between releasing what it has read.
const SLICE: usize = 1 << 20;
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
    chunks: Vec<Chunk>,
    rows: Vec<u64>,
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
/// PROF: also returns (scan end ns, documents, stream length, stream capacity).
fn scan_chunk(data: &[u8], lo: usize, hi: usize, plan: &Plan, rows: &[AtomicU64]) -> (Chunk, [u64; 4]) {
    let first = id_at(data, lo);
    let (nl, words) = (plan.nlist, rows.len() / plan.nbm.max(1));
    // The list-term ids of each document, each document ended by u16::MAX.
    let mut stream = Vec::with_capacity((hi - lo) / 16);
    let (mut hits, mut doc, mut new, mut anch) = (Vec::new(), first, Vec::new(), Vec::new());
    // The bitmap words of the current 64 documents, stored when they are done.
    let mut group = vec![0u64; plan.nbm];
    let flush = |group: &mut [u64], doc: u32| {
        for (b, x) in group.iter_mut().enumerate() {
            rows[b * words + doc as usize / 64].store(std::mem::take(x), Relaxed);
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
    let prof = [ns(), (doc - first) as u64, stream.len() as u64, stream.capacity() as u64]; // PROF
    // Counting sort of the stream, dropping a term's repeats within a document.
    let mut offs = vec![0u32; nl + 1];
    stream
        .iter()
        .filter(|&&l| l != u16::MAX)
        .for_each(|&l| offs[l as usize + 1] += 1);
    (1..=nl).for_each(|l| offs[l] += offs[l - 1]);
    let (mut end, mut docs, mut d) = (offs.clone(), vec![0u16; offs[nl] as usize], 0u16);
    for l in stream {
        if l == u16::MAX {
            d = d.wrapping_add(1);
        } else {
            let e = &mut end[l as usize];
            if *e == offs[l as usize] || docs[*e as usize - 1] != d {
                docs[*e as usize] = d;
                *e += 1;
            }
        }
    }
    // Close the gaps the repeats left.
    let mut w = 0;
    for l in 0..nl {
        let (a, b) = (offs[l] as usize, end[l] as usize);
        docs.copy_within(a..b, w);
        offs[l] = w as u32;
        w += b - a;
    }
    offs[nl] = w as u32;
    (Chunk { first, offs, docs, hits }, prof)
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
/// PROF: returns whether the running result was ever the bitmap.
fn boolean(q: &[(u8, u32)], plan: &Plan, s: &mut Scratch, out: &mut String) -> bool {
    let mut used = false; // PROF
    let (chunks, rows) = (&plan.chunks, &plan.rows);
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
                    used = true; // PROF
                }
                (true, b'A') => bm.iter_mut().zip(row).for_each(|(x, y)| *x &= y),
                (true, b'N') => bm.iter_mut().zip(row).for_each(|(x, y)| *x &= !y),
                _ => bm.iter_mut().zip(row).for_each(|(x, y)| *x |= y),
            }
            continue;
        }
        let df: usize = chunks.iter().map(|c| c.post(t).len()).sum();
        let and = op == b'A';
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
            used = true; // PROF
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
        let sum = r.iter().map(|&d| d as u64).sum();
        line(out, r.len(), sum, r.iter().copied());
        return used; // PROF
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
    line(out, n, sum, ids);
    bm.fill(0);
    used // PROF
}

/// Per-thread buffers for answering queries.
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
    T0.set(std::time::Instant::now()).unwrap(); // PROF
    let mut log = String::new(); // PROF
    let smp = sampler(); // PROF
    let data_dir = env::var("SD_DATA").unwrap_or_else(|_| "/data".into());
    let out_dir = env::var("SD_OUT").unwrap_or_else(|_| "/out".into());
    let nthreads = env::var("SD_THREADS").ok().and_then(|s| s.parse().ok());
    let nthreads = nthreads.unwrap_or_else(|| thread::available_parallelism().map_or(4, |n| n.get()));

    let qtext = fs::read(format!("{data_dir}/queries.txt")).expect("read queries.txt");
    phase(&mut log, "read_queries"); // PROF
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
    phase(&mut log, "parse_intern"); // PROF
    let data = map_file(&format!("{data_dir}/docs.txt"));
    phase(&mut log, "mmap"); // PROF

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
    phase(&mut log, "sample_scan"); // PROF
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
    phase(&mut log, "plan_build"); // PROF

    // Equal byte ranges, each moved to the next line whose id is a multiple
    // of 64; at most 65,536 lines per chunk.
    let ndocs = data.len().checked_sub(1).map_or(0, |e| id_at(data, line_start(data, data[..e].iter().rposition(|&b| b == b'\n').map_or(0, |p| p + 1))) as usize + 1);
    let words = ndocs.div_ceil(64);
    // Zeroed pages straight from the OS, touched first by the scanning threads.
    let mut rows = std::mem::ManuallyDrop::new(vec![0u64; plan.nbm * words]);
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
    let claim = |n| (0..).map(|_| next.fetch_add(1, Relaxed)).take_while(move |&k| k < n);
    phase(&mut log, "rows_alloc"); // PROF
    // PROF: per chunk `IDX <thread> <chunk> <ndocs> <bytes> <t_start> <t_scan_end>
    // <t_csr_end> <stream_len> <stream_cap> <nhits> <ndocs_entries>`, buffered per thread.
    let idx: Vec<(Vec<(usize, Chunk)>, String)> = par(nthreads, |th| {
        let mut tlog = String::new();
        let v = claim(nchunks)
            .map(|k| {
                let t0 = ns();
                let (lo, hi) = (cut(k), cut(k + 1));
                let (c, p) = scan_chunk(data, lo, hi, &plan, &rows);
                let t2 = ns();
                writeln!(tlog, "IDX {th} {k} {} {} {t0} {} {t2} {} {} {} {}", p[1], hi - lo, p[0], p[2], p[3], c.hits.len(), c.docs.len()).unwrap();
                (k, c)
            })
            .collect::<Vec<_>>();
        (v, tlog)
    });
    phase(&mut log, "index"); // PROF
    let mut idx_log = String::new(); // PROF
    let mut chunks: Vec<_> = idx.into_iter().flat_map(|(v, l)| { idx_log += &l; v }).collect();
    chunks.sort_unstable_by_key(|c| c.0);
    plan.chunks = chunks.into_iter().map(|c| c.1).collect();
    plan.rows = rows.into_iter().map(AtomicU64::into_inner).collect();
    phase(&mut log, "chunk_sort"); // PROF
    // Phrase matches by query, each in ascending id order.
    let mut hits: Vec<(u32, u32)> = plan.chunks.iter().flat_map(|c| c.hits.iter().copied()).collect();
    hits.sort_by_key(|h| h.0);
    let mut hoff = vec![0usize; queries.len() + 1];
    hits.iter().for_each(|h| hoff[h.0 as usize + 1] += 1);
    (1..hoff.len()).for_each(|i| hoff[i] += hoff[i - 1]);
    phase(&mut log, "hits_collect"); // PROF

    // Answer blocks of queries, claimed by the threads in turn.
    next.store(0, Relaxed);
    let block = 64;
    // PROF: kinds 0 bool_list (no bitmap term, list result), 1 bool_list_bm (no bitmap
    // term, switched to the bitmap by a large OR), 2 bool_row_list (a bitmap term, list
    // result), 3 bool_row_bm (a bitmap term and the bitmap result), 4 phrase.
    let ans: Vec<_> = par(nthreads, |th| {
        let mut s = Scratch { list: vec![], tmp: vec![], out: vec![], bm: vec![0; words] };
        let (mut tlog, mut per, mut tb, mut tp, mut nb, mut np) = (String::new(), Vec::new(), 0u64, 0u64, 0u64, 0u64);
        let v = claim(queries.len().div_ceil(block))
            .map(|b| {
                let t0 = ns();
                let (bnb, bnp) = (nb, np);
                let mut out = String::new();
                for qi in b * block..((b + 1) * block).min(queries.len()) {
                    let qt = std::time::Instant::now(); // PROF
                    match &queries[qi] {
                        Query::Bool(q) => {
                            let used = boolean(q, &plan, &mut s, &mut out);
                            let d = qt.elapsed().as_nanos() as u64;
                            let row = q.iter().any(|&(_, t)| plan.role[t as usize] & BITMAP != 0);
                            per.push((d, qi as u32, row as u8 * 2 + used as u8, q.len() as u32));
                            (tb, nb) = (tb + d, nb + 1);
                        }
                        Query::Phrase(p) => {
                            let mut d: Vec<u32> = hits[hoff[qi]..hoff[qi + 1]].iter().map(|h| h.1).collect();
                            d.dedup(); // a phrase can occur twice in a document
                            line(&mut out, d.len(), d.iter().map(|&x| x as u64).sum(), d.into_iter());
                            let d = qt.elapsed().as_nanos() as u64;
                            per.push((d, qi as u32, 4, p.len() as u32));
                            (tp, np) = (tp + d, np + 1);
                        }
                    }
                }
                writeln!(tlog, "BLOCK {th} {b} {} {} {t0} {}", nb - bnb, np - bnp, ns()).unwrap();
                (b, out)
            })
            .collect::<Vec<_>>();
        writeln!(tlog, "QTHREAD {th} {tb} {tp} {nb} {np}").unwrap();
        (v, tlog, per)
    });
    phase(&mut log, "answer"); // PROF
    let (mut ans_log, mut per) = (String::new(), Vec::new()); // PROF
    let mut outs: Vec<(usize, String)> = ans.into_iter().flat_map(|(v, l, p)| { ans_log += &l; per.extend(p); v }).collect();
    outs.sort_unstable_by_key(|o| o.0);
    let out: String = outs.into_iter().map(|o| o.1).collect();
    phase(&mut log, "outs_sort_concat"); // PROF
    let out_len = out.len(); // PROF
    fs::create_dir_all(&out_dir).ok();
    fs::write(format!("{out_dir}/results.txt"), out).expect("write results.txt");
    phase(&mut log, "write"); // PROF

    // PROF: everything below only reports; it runs after the last phase mark.
    log += &idx_log;
    log += &ans_log;
    let kinds = ["bool_list", "bool_list_bm", "bool_row_list", "bool_row_bm", "phrase"];
    for (k, name) in kinds.iter().enumerate() {
        let v: Vec<u64> = per.iter().filter(|p| p.2 as usize == k).map(|p| p.0).collect();
        let cl: u64 = per.iter().filter(|p| p.2 as usize == k).map(|p| p.3 as u64).sum();
        writeln!(log, "QKIND {name} {} {} {} {cl}", v.len(), v.iter().sum::<u64>(), v.iter().max().unwrap_or(&0)).unwrap();
    }
    per.sort_unstable_by_key(|p| std::cmp::Reverse(p.0));
    for p in per.iter().take(20) {
        writeln!(log, "QSLOW {} {} {} {}", p.1, p.0, kinds[p.2 as usize], p.3).unwrap();
    }
    let nbool = queries.iter().filter(|q| matches!(q, Query::Bool(_))).count();
    let cs = &plan.chunks;
    let info: Vec<(&str, usize)> = vec![
        ("nqueries", queries.len()),
        ("nbool", nbool),
        ("nphrase", queries.len() - nbool),
        ("bool_clauses", queries.iter().map(|q| if let Query::Bool(v) = q { v.len() } else { 0 }).sum()),
        ("phrase_terms", queries.iter().map(|q| if let Query::Phrase(v) = q { v.len() } else { 0 }).sum()),
        ("nterms", plan.role.len()),
        ("nlist", plan.nlist),
        ("nbm", plan.nbm),
        ("nlong", plan.long.len()),
        ("key_slots", plan.keys.len()),
        ("sample_docs", sdocs as usize),
        ("sample_bytes", line_start(data, SAMPLE)),
        ("ndocs", ndocs),
        ("words", words),
        ("nchunks", nchunks),
        ("nthreads", nthreads),
        ("data_len", data.len()),
        ("queries_bytes", qtext.len()),
        ("anchors", plan.anchors.len()),
        ("anchor_terms", (0..plan.role.len()).filter(|&t| plan.role[t] & ANCHOR != 0).count()),
        ("rows_bytes", plan.rows.len() * 8),
        ("chunk_docs_entries", cs.iter().map(|c| c.docs.len()).sum()),
        ("chunk_docs_bytes", cs.iter().map(|c| c.docs.len() * 2).sum()),
        ("chunk_docs_cap_bytes", cs.iter().map(|c| c.docs.capacity() * 2).sum()),
        ("chunk_offs_bytes", cs.iter().map(|c| c.offs.len() * 4).sum()),
        ("chunk_hits_bytes", cs.iter().map(|c| c.hits.capacity() * 8).sum()),
        ("hits", hits.len()),
        ("hits_bytes", hits.capacity() * 8),
        ("hoff_bytes", hoff.len() * 8),
        ("plan_keys_bytes", plan.keys.len() * 24),
        ("plan_role_bytes", plan.role.len()),
        ("plan_aoff_bytes", plan.aoff.len() * 4),
        ("plan_anchors_bytes", plan.anchors.len() * 16),
        ("plan_flat_bytes", plan.flat.len() * 4),
        ("queries_vec_bytes", queries.iter().map(|q| match q { Query::Bool(v) => v.capacity() * 8, Query::Phrase(v) => v.capacity() * 4 } + 32).sum()),
        ("sample_freq_bytes", freq.len() * 4 * 3),
        ("outs_bytes", out_len),
        ("results_bytes", out_len),
        ("scratch_bm_bytes_per_thread", words * 8),
    ];
    for (k, v) in info {
        writeln!(log, "INFO {k} {v}").unwrap();
    }
    if let Some(h) = smp {
        SAMPLER_STOP.store(true, Relaxed);
        log += &h.join().unwrap();
    }
    mem_line(&mut log, "exit");
    eprint!("{log}");
    std::process::exit(0); // the OS frees everything faster than the destructors
}
