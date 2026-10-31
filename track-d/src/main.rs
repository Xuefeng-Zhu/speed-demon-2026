//! Speed Demon 2026, Track D (Traverse): exact shortest paths on a 5M-edge graph.
//!
//! 1. `graph.txt` is mapped into memory; every thread parses its own slice
//!    and buckets each edge by the block of node ids its tail falls in.
//!    Thread j then turns block j into its slice of a CSR graph. An edge is
//!    one u32: the head in the low bits, the weight in the rest, or an escape
//!    code for the rare weight that does not fit (looked up in a sorted list).
//! 2. The file's ids carry no locality, so nodes are renumbered: threads
//!    grow breadth-first clusters of nearby nodes and number each cluster
//!    contiguously. The forward graph's rows are moved to the new ids, and
//!    the backward graph is built from it.
//! 3. Threads pull queries from a shared counter and answer each with a
//!    bidirectional Dijkstra search that expands the side with the smaller
//!    heap. It keeps u32 distances in blocks handed out on demand, so twelve
//!    threads need little memory; a query whose answer may not fit in u32 is
//!    run again with u64 distances.
//!
//! Std only (plus libc's `mmap`, `madvise` and `mallopt`, which std links).
//! Override the directories with `SD_DATA` and `SD_OUT`.

use std::sync::atomic::{AtomicI64, AtomicU32, AtomicUsize, Ordering::Relaxed};
use std::{fs, fs::File, os::fd::AsRawFd, thread};

extern "C" {
    fn mmap(addr: *mut u8, len: usize, prot: i32, flags: i32, fd: i32, off: i64) -> *mut u8;
    fn mallopt(param: i32, value: i32) -> i32;
    fn madvise(addr: *mut u8, len: usize, advice: i32) -> i32;
}

/// Runs `f(i)` for every `i < threads`, each on its own thread, and returns
/// the results in order of `i`.
fn parallel<T: Send>(threads: usize, f: &(impl Fn(usize) -> T + Sync)) -> Vec<T> {
    thread::scope(|sc| {
        let handles: Vec<_> = (0..threads).map(|i| sc.spawn(move || f(i))).collect();
        handles.into_iter().map(|h| h.join().unwrap()).collect()
    })
}

/// A view of `v` that threads can write at once (same layout as `u32`).
fn atomic(v: &mut [u32]) -> &[AtomicU32] {
    unsafe { &*(v as *mut [u32] as *const [AtomicU32]) }
}

/// `len` zeros, on huge pages where the kernel allows: fewer page faults to
/// fill the array and fewer TLB misses to search it.
fn zeros(len: usize) -> Vec<u32> {
    let v = vec![0u32; len];
    let huge = |p: usize| (v.as_ptr() as usize + p) & !((1 << 21) - 1);
    let (a, b) = (huge((1 << 21) - 1), huge(len * 4));
    if a < b {
        unsafe { madvise(a as *mut u8, b - a, 14) }; // MADV_HUGEPAGE
    }
    v
}

/// Parses the number at `text[*p..]` and steps past the byte after it. Up to
/// 7 digits come from one 8-byte load: digits are the bytes with bit 4 set,
/// and three multiplies combine them. Longer numbers, and the file's last
/// bytes, go digit by digit.
fn num(text: &[u8], p: &mut usize) -> u32 {
    if let Some(b) = text.get(*p..*p + 8) {
        let x = u64::from_le_bytes(b.try_into().unwrap());
        let len = (!x & 0x1010_1010_1010_1010).trailing_zeros() as usize / 8;
        if len < 8 {
            let v = (x << (64 - 8 * len)) & 0x0f0f_0f0f_0f0f_0f0f;
            let v = (v * 10 + (v >> 8)) & 0x00ff_00ff_00ff_00ff;
            let v = (v * 100 + (v >> 16)) & 0x0000_ffff_0000_ffff;
            *p += len + 1;
            return (v * 10000 + (v >> 32)) as u32;
        }
    }
    let mut v = 0;
    while text[*p] > b' ' {
        v = v * 10 + (text[*p] - b'0') as u32;
        *p += 1;
    }
    *p += 1;
    v
}

/// Calls `f(u, v, w)` for every `u v w` line in `text[p..end]`.
fn each_edge(text: &[u8], mut p: usize, end: usize, mut f: impl FnMut(u32, u32, u32)) {
    while p < end {
        let (u, v) = (num(text, &mut p), num(text, &mut p));
        f(u, v, num(text, &mut p));
    }
}

/// Compressed sparse rows: the edges out of `u` are `adj[first[u]..first[u + 1]]`,
/// each packed as `head | code << bits`, where `code` is the weight, or `wide`
/// (all ones) for a weight that does not fit, found in `Net::wide` instead.
struct Csr {
    first: Vec<u32>,
    adj: Vec<u32>,
}

fn edges(g: &Csr, u: usize) -> &[u32] {
    &g.adj[g.first[u] as usize..g.first[u + 1] as usize]
}

/// The two graphs (forward, backward), in the new ids, plus the encoding.
struct Net {
    graphs: [Csr; 2],
    bits: u32,
    /// `(tail << 32 | head, lightest weight)` of every forward edge whose
    /// weight is `wide` or more, sorted.
    wide: Vec<(u64, u32)>,
}

/// Turns per-node counts into running sums, so `first[u]` is the end of u's
/// edges; threads then place each edge by taking one off its tail's end.
fn ends(first: &[AtomicU32]) {
    first.iter().fold(0, |sum, c| {
        c.store(c.load(Relaxed) + sum, Relaxed);
        c.load(Relaxed)
    });
}

/// The forward graph in the file's ids, plus the edges with wide weights as
/// (tail, head, weight). The file is mapped, not read: its pages are already
/// cached and are not charged to this process. Thread i parses the lines that
/// start in its share of the bytes and buckets each edge, packed into a u64,
/// by the block of ids its tail falls in; thread j then turns block j into
/// its slice of the arrays with a counting sort, so no atomics are needed and
/// each thread writes a small window of memory.
fn load_graph(path: &str, threads: usize) -> (Csr, u32, Vec<(u32, u32, u32)>) {
    let file = File::open(path).unwrap();
    let len = file.metadata().unwrap().len() as usize;
    let ptr = unsafe { mmap(std::ptr::null_mut(), len, 1, 2, file.as_raw_fd(), 0) };
    let text = unsafe { std::slice::from_raw_parts(ptr, len) };
    let line_end = |p: usize| p + text[p..].iter().position(|&b| b == b'\n').map_or(len - p, |i| i + 1);
    let mut p = 0;
    let (n, m) = (num(text, &mut p) as usize, num(text, &mut p) as usize);
    let bits = 32 - (n as u32).leading_zeros();
    let wide = u32::MAX >> bits;
    let cuts: Vec<usize> = (0..=threads).map(|i| line_end((i * len / threads).max(1) - 1)).collect();
    let block_len = n.div_ceil(threads);
    let parts = parallel(threads, &|i| {
        // Sized for an even spread, so the lists rarely have to grow.
        let cap = m / threads / threads * 9 / 8 + 64;
        let mut lists: Vec<Vec<u64>> = (0..threads).map(|_| Vec::with_capacity(cap)).collect();
        let mut big = Vec::new();
        each_edge(text, cuts[i], cuts[i + 1], |u, v, w| {
            lists[u as usize / block_len].push((u as u64) << 32 | (v | w.min(wide) << bits) as u64);
            if w >= wide {
                big.push((u, v, w));
            }
        });
        (lists, big)
    });
    let (mut buckets, big): (Vec<_>, Vec<_>) = parts.into_iter().unzip();
    let (mut first, mut adj) = (zeros(n + 1), zeros(m));
    let (mut adj_rest, mut start) = (&mut adj[..], 0);
    thread::scope(|sc| {
        for (j, first) in first[..n].chunks_mut(block_len).enumerate() {
            let col: Vec<_> = buckets.iter_mut().map(|b| std::mem::take(&mut b[j])).collect();
            let size: usize = col.iter().map(Vec::len).sum();
            let (adj, rest) = std::mem::take(&mut adj_rest).split_at_mut(size);
            let lo = j * block_len;
            adj_rest = rest;
            sc.spawn(move || {
                col.iter().flatten().for_each(|&e| first[(e >> 32) as usize - lo] += 1);
                first.iter_mut().fold(start, |sum, c| {
                    *c += sum;
                    *c
                });
                for list in col {
                    for e in list {
                        let c = &mut first[(e >> 32) as usize - lo];
                        *c -= 1;
                        adj[(*c - start) as usize] = e as u32;
                    }
                }
            });
            start += size as u32;
        }
    });
    first[n] = m as u32;
    (Csr { first, adj }, bits, big.concat())
}

/// Nodes per cluster: a ball of this many nodes fills a few pages of the
/// distance array.
const CLUSTER: usize = 1024;

/// Distance slots come in blocks of `1 << BLOCK` node ids.
const BLOCK: u32 = 6;

/// The new id of every node. Thread i scans its share of the ids for
/// unclaimed roots and grows breadth-first clusters of up to `CLUSTER` nodes
/// from them, seeding the next cluster on the frontier of the last; each
/// finished cluster takes the next free run of ids, so nearby nodes get
/// nearby ids. Nodes are claimed atomically;
/// which thread wins a node changes the numbering but never an answer.
fn renumber(g: &Csr, bits: u32, threads: usize) -> Vec<u32> {
    let n = g.first.len() - 1;
    let mut rank = vec![u32::MAX; n];
    let r = atomic(&mut rank);
    let claim = |v: usize| r[v].load(Relaxed) == u32::MAX && r[v].compare_exchange(u32::MAX, 0, Relaxed, Relaxed).is_ok();
    let next = AtomicU32::new(0);
    parallel(threads, &|i| {
        let mut roots = i * n / threads..(i + 1) * n / threads;
        let (mut mine, mut seed) = (Vec::with_capacity(CLUSTER), None);
        while let Some(root) = seed.take().filter(|&v| claim(v)).or_else(|| roots.find(|&v| claim(v))) {
            mine.push(root as u32);
            let mut k = 0;
            'grow: while k < mine.len() {
                for &e in edges(g, mine[k] as usize) {
                    let v = (e & ((1 << bits) - 1)) as usize;
                    if mine.len() == CLUSTER {
                        seed = Some(v);
                        break 'grow;
                    }
                    if claim(v) {
                        mine.push(v as u32);
                    }
                }
                k += 1;
            }
            // The cluster is complete: number it.
            let base = next.fetch_add(mine.len() as u32, Relaxed);
            for (k, v) in mine.drain(..).enumerate() {
                r[v as usize].store(base + k as u32, Relaxed);
            }
        }
    });
    rank
}

/// The forward and backward graphs of `g` in the new ids. Forward rows are
/// `g`'s rows moved to their new places; the backward graph is then built
/// from the forward one, after `g` and `rank` are gone.
fn relabel(g: Csr, rank: Vec<u32>, bits: u32, threads: usize) -> [Csr; 2] {
    let (n, m, mask) = (rank.len(), g.adj.len(), (1 << bits) - 1);
    let span = |i: usize| i * n / threads..(i + 1) * n / threads;
    let (mut first, mut adj) = (zeros(n + 1), zeros(m));
    let f = atomic(&mut first);
    parallel(threads, &|i| span(i).for_each(|u| f[rank[u] as usize].store(edges(&g, u).len() as u32, Relaxed)));
    ends(f);
    let a = atomic(&mut adj);
    parallel(threads, &|i| {
        for u in span(i) {
            let end = &f[rank[u] as usize];
            let mut p = end.load(Relaxed);
            for &e in edges(&g, u) {
                p -= 1;
                a[p as usize].store(rank[(e & mask) as usize] | e & !mask, Relaxed);
            }
            end.store(p, Relaxed);
        }
    });
    drop((g, rank));
    let fwd = Csr { first, adj };
    let (mut first, mut adj) = (zeros(n + 1), zeros(m));
    let f = atomic(&mut first);
    let mine = |i: usize| span(i).flat_map(|u| edges(&fwd, u).iter().map(move |&e| (u as u32, e)));
    parallel(threads, &|i| mine(i).for_each(|(_, e)| _ = f[(e & mask) as usize].fetch_add(1, Relaxed)));
    ends(f);
    let a = atomic(&mut adj);
    parallel(threads, &|i| {
        for (u, e) in mine(i) {
            let p = f[(e & mask) as usize].fetch_sub(1, Relaxed) - 1;
            a[p as usize].store(u | e & !mask, Relaxed);
        }
    });
    [fwd, Csr { first, adj }]
}

/// A tentative distance as stored: the bitwise complement, so that zero
/// means "not reached". `u32` slots halve the memory of a search; a distance
/// that does not fit is refused, and the query is then run again with `u64`.
trait Dist: Copy + Default {
    fn get(self) -> u64;
    fn put(d: u64) -> Option<Self>;
}

impl Dist for u32 {
    fn get(self) -> u64 {
        [!self as u64, u64::MAX][(self == 0) as usize]
    }
    fn put(d: u64) -> Option<u32> {
        (d < u32::MAX as u64).then(|| !(d as u32))
    }
}

impl Dist for u64 {
    fn get(self) -> u64 {
        !self
    }
    fn put(d: u64) -> Option<u64> {
        Some(!d)
    }
}

/// Per-thread search state, reused between queries. Distances live in
/// blocks of `1 << BLOCK` consecutive node ids, handed out from `pool` as a
/// search first reaches each block (`map` gives a block's offset in `pool`,
/// `owners` lists the blocks in use), so a thread's memory is the footprint
/// of its biggest search rather than a slot for every node. A slot holds the
/// forward and backward tentative distances side by side, as bitwise
/// complements: zero means "not reached".
struct Search<D> {
    map: Vec<u32>,
    pool: Vec<[D; 2]>,
    owners: Vec<u32>,
    size: [usize; 2],
    heaps: [RadixHeap; 2],
    /// Whether this search refused a distance too long for `D`.
    cut: bool,
}

impl<D: Dist> Search<D> {
    fn new(n: usize) -> Self {
        Search {
            map: vec![u32::MAX; (n >> BLOCK) + 1],
            pool: Vec::new(),
            owners: Vec::new(),
            size: [0; 2],
            heaps: [(); 2].map(|_| RadixHeap {
                last: 0,
                buckets: std::array::from_fn(|_| Vec::new()),
            }),
            cut: false,
        }
    }

    fn slot(&mut self, v: u32) -> usize {
        let block = (v >> BLOCK) as usize;
        if self.map[block] == u32::MAX {
            self.map[block] = (self.owners.len() << BLOCK) as u32;
            self.owners.push(block as u32);
            self.pool.resize(self.pool.len().max(self.owners.len() << BLOCK), [D::default(); 2]);
        }
        self.map[block] as usize | (v as usize & ((1 << BLOCK) - 1))
    }

    /// Lowers `v`'s distance on `side` to `d` if that is shorter; returns its slot.
    fn reach(&mut self, side: usize, v: u32, d: u64) -> usize {
        let i = self.slot(v);
        if d < self.pool[i][side].get() {
            match D::put(d) {
                Some(x) => {
                    self.pool[i][side] = x;
                    self.size[side] += 1;
                    self.heaps[side].push(d, v);
                }
                None => self.cut = true,
            }
        }
        i
    }

    /// Bidirectional Dijkstra: expand the side whose heap holds fewer entries,
    /// keep the best s-t path seen where the two searches meet, and stop once
    /// no shorter one can exist. Balancing by heap size rather than by key
    /// matters when one side is boxed in behind huge weights: that side then
    /// runs dry at once, instead of the other side exploring the whole graph
    /// below the huge key first. Returns `u64::MAX` when `t` is unreachable.
    fn distance(&mut self, net: &Net, s: u32, t: u32) -> u64 {
        let (mask, wide) = ((1 << net.bits) - 1, u32::MAX >> net.bits);
        self.cut = false;
        self.reach(0, s, 0);
        self.reach(1, t, 0);
        let mut best = if s == t { 0 } else { u64::MAX };
        while let (Some(a), Some(b)) = (self.heaps[0].top(), self.heaps[1].top()) {
            if a.saturating_add(b) >= best {
                break;
            }
            let side = (self.size[0] > self.size[1]) as usize;
            let (d, u) = self.heaps[side].buckets[0].pop().unwrap();
            self.size[side] -= 1;
            let i = self.slot(u);
            if d > self.pool[i][side].get() {
                continue; // stale entry
            }
            for &e in edges(&net.graphs[side], u as usize) {
                let (v, mut w) = (e & mask, e >> net.bits);
                if w == wide {
                    let key = [(u as u64) << 32 | v as u64, (v as u64) << 32 | u as u64][side];
                    w = net.wide[net.wide.binary_search_by_key(&key, |x| x.0).unwrap()].1;
                }
                let dv = d + w as u64;
                let i = self.reach(side, v, dv);
                // An unreached other side reads as u64::MAX, which saturates.
                best = best.min(dv.saturating_add(self.pool[i][1 - side].get()));
            }
        }
        self.pool[..self.owners.len() << BLOCK].fill([D::default(); 2]);
        for block in self.owners.drain(..) {
            self.map[block as usize] = u32::MAX;
        }
        // A stale `last` is harmless: the next search's first `top` sees one
        // entry per heap and resets `last` to its key.
        for heap in &mut self.heaps {
            heap.buckets.iter_mut().for_each(Vec::clear);
        }
        self.size = [0; 2];
        best
    }
}

/// Monotone priority queue: keys pushed are never below the last key popped.
/// Bucket i holds keys whose highest bit differing from `last` is bit i - 1.
struct RadixHeap {
    last: u64,
    buckets: [Vec<(u64, u32)>; 65],
}

impl RadixHeap {
    fn push(&mut self, k: u64, v: u32) {
        self.buckets[64 - (k ^ self.last).leading_zeros() as usize].push((k, v));
    }

    /// The smallest key, after moving every entry with that key into bucket 0.
    fn top(&mut self) -> Option<u64> {
        if self.buckets[0].is_empty() {
            let i = self.buckets.iter().position(|b| !b.is_empty())?;
            let mut b = std::mem::take(&mut self.buckets[i]);
            self.last = b.iter().map(|e| e.0).min().unwrap();
            b.drain(..).for_each(|(k, v)| self.push(k, v));
            self.buckets[i] = b; // keeps its allocation
        }
        Some(self.last)
    }
}

fn main() {
    let dir = |key, default: &str| std::env::var(key).unwrap_or(default.into());
    let (data, out) = (dir("SD_DATA", "/data"), dir("SD_OUT", "/out"));
    // M_MMAP_THRESHOLD: big blocks (the edge buckets) go straight back to
    // the kernel when freed, instead of lingering in per-thread arenas.
    unsafe { mallopt(-3, 1 << 17) };
    let threads = 6;
    let (g, bits, big) = load_graph(&format!("{data}/graph.txt"), threads);
    let rank = renumber(&g, bits, threads);
    let r = |v: u32| rank[v as usize];
    let (text, mut p, mut ids) = (fs::read(format!("{data}/queries.txt")).unwrap(), 0, vec![]);
    while p < text.len() {
        ids.push(r(num(&text, &mut p)));
    }
    let key = |u, v| (r(u) as u64) << 32 | r(v) as u64;
    let mut wide: Vec<_> = big.iter().map(|&(u, v, w)| (key(u, v), w)).collect();
    wide.sort_unstable();
    wide.dedup_by_key(|x| x.0);
    let n = rank.len();
    let net = Net { graphs: relabel(g, rank, bits, threads), bits, wide };
    let answers: Vec<AtomicI64> = (0..ids.len() / 2).map(|_| AtomicI64::new(0)).collect();
    let next = AtomicUsize::new(0);
    parallel(threads, &|_| {
        let (mut narrow, mut wide) = (Search::<u32>::new(n), None);
        let mut i = next.fetch_add(1, Relaxed);
        while let Some(&[s, t]) = ids.get(2 * i..2 * i + 2) {
            let mut d = narrow.distance(&net, s, t);
            if narrow.cut && d >= u32::MAX as u64 {
                d = wide.get_or_insert_with(|| Search::<u64>::new(n)).distance(&net, s, t);
            }
            // An unreachable target's u64::MAX becomes the -1 the output wants.
            answers[i].store(d as i64, Relaxed);
            i = next.fetch_add(1, Relaxed);
        }
    });
    let lines = answers.iter().map(|a| format!("{}\n", a.load(Relaxed)));
    fs::write(format!("{out}/distances.txt"), lines.collect::<String>()).unwrap();
}
