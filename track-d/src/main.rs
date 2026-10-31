//! Speed Demon 2026, Track D (Traverse): exact shortest paths on a 5M-edge graph.
//!
//! 1. `graph.txt` is mapped into memory; every thread parses its own slice
//!    and buckets each edge by the block of node ids its tail falls in.
//!    Thread j then turns block j into its slice of a CSR graph.
//! 2. The file's ids carry no locality, so nodes are renumbered: threads
//!    grow breadth-first clusters of nearby nodes and number each cluster
//!    contiguously. The forward and backward graphs are rebuilt in the new ids.
//! 3. Threads pull queries from a shared counter and answer each with a
//!    bidirectional Dijkstra search that expands the side with the smaller
//!    heap. It keeps its distances in blocks handed out on demand, so twelve
//!    threads need little memory.
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

/// Parses whitespace-separated unsigned decimals. A trailing separator yields
/// one extra 0, which "take three (or two) at a time" ignores.
fn numbers(s: &[u8]) -> impl Iterator<Item = u32> + '_ {
    s.split(|&b| b <= b' ')
        .map(|t| t.iter().fold(0, |x, &b| x * 10 + (b - b'0') as u32))
}

/// Runs `f(i)` for every `i < threads`, each on its own thread, and returns
/// the results in order of `i`.
fn parallel<T: Send>(threads: usize, f: &(impl Fn(usize) -> T + Sync)) -> Vec<T> {
    thread::scope(|sc| {
        let handles: Vec<_> = (0..threads).map(|i| sc.spawn(move || f(i))).collect();
        handles.into_iter().map(|h| h.join().unwrap()).collect()
    })
}

/// Compressed sparse rows `(first, adj)`: the edges out of `u` are
/// `adj[first[u]..first[u + 1]]`, each packed as `weight << 32 | head`.
type Csr = (Vec<u32>, Vec<u64>);

fn edges(g: &Csr, u: usize) -> &[u64] {
    &g.1[g.0[u] as usize..g.0[u + 1] as usize]
}

/// One thread's edges as (tail, head, weight), by block of the tail: block j
/// is the `block_len` node ids from `j * block_len` on.
struct Buckets {
    block_len: usize,
    lists: Vec<Vec<(u32, u32, u32)>>,
}

impl Buckets {
    fn push(&mut self, u: u32, v: u32, w: u32) {
        self.lists[u as usize / self.block_len].push((u, v, w));
    }
}

/// A CSR graph of n nodes and m edges. Thread i hands its share of the edges
/// to `fill`, which buckets them by block of the tail; then thread j turns
/// block j into its slice of the arrays with a counting sort, so no atomics
/// are needed and each thread writes a small window of memory.
fn build(n: usize, m: usize, threads: usize, fill: &(impl Fn(usize, &mut Buckets) + Sync)) -> Csr {
    let block_len = n.div_ceil(threads);
    let mut buckets = parallel(threads, &|i| {
        // Sized for an even spread, so the lists rarely have to grow.
        let cap = m / threads / threads * 9 / 8 + 64;
        let lists = (0..threads).map(|_| Vec::with_capacity(cap)).collect();
        let mut b = Buckets { block_len, lists };
        fill(i, &mut b);
        b.lists
    });
    let (mut first, mut adj) = (vec![0u32; n + 1], vec![0u64; m]);
    // Huge pages, where the kernel allows: fewer page faults to fill the
    // edges and fewer TLB misses to search them.
    let huge = |p: usize| p & !((1 << 21) - 1);
    let (a, b) = (huge(adj.as_ptr() as usize + (1 << 21) - 1), huge(adj.as_ptr() as usize + m * 8));
    if a < b {
        unsafe { madvise(a as *mut u8, b - a, 14) }; // MADV_HUGEPAGE
    }
    let (mut adj_rest, mut start) = (&mut adj[..], 0);
    thread::scope(|sc| {
        for (j, first) in first[..n].chunks_mut(block_len).enumerate() {
            // Thread j takes block j's buckets and frees them when done.
            let col: Vec<_> = buckets.iter_mut().map(|b| std::mem::take(&mut b[j])).collect();
            let size: usize = col.iter().map(Vec::len).sum();
            let (adj, rest) = std::mem::take(&mut adj_rest).split_at_mut(size);
            let lo = j * block_len;
            adj_rest = rest;
            sc.spawn(move || {
                let edges = || col.iter().flatten();
                edges().for_each(|&(u, _, _)| first[u as usize - lo] += 1);
                // Running sums make `first[u]` the end of u's edges; placing
                // each edge then walks it back down to the start.
                first.iter_mut().fold(start, |sum, c| {
                    *c += sum;
                    *c
                });
                for &(u, v, w) in edges() {
                    first[u as usize - lo] -= 1;
                    adj[(first[u as usize - lo] - start) as usize] = (w as u64) << 32 | v as u64;
                }
            });
            start += size as u32;
        }
    });
    first[n] = m as u32;
    (first, adj)
}

/// The forward graph, in the file's node ids. `graph.txt` is mapped, not
/// read: the page cache is already warm, and mapped file pages are not
/// charged to this process the way a heap copy would be.
fn load_graph(path: &str, threads: usize) -> Csr {
    let file = File::open(path).unwrap();
    let len = file.metadata().unwrap().len() as usize;
    let ptr = unsafe { mmap(std::ptr::null_mut(), len, 1, 2, file.as_raw_fd(), 0) };
    let text = unsafe { std::slice::from_raw_parts(ptr, len) };
    let line_end = |p: usize| p + text[p..].iter().position(|&b| b == b'\n').map_or(len - p, |i| i + 1);
    let header: Vec<u32> = numbers(&text[..line_end(0)]).take(2).collect();
    // Thread i parses the lines that start in its share of the bytes.
    let cuts: Vec<usize> = (0..=threads).map(|i| line_end((i * len / threads).max(1) - 1)).collect();
    build(header[0] as usize, header[1] as usize, threads, &|i, b| {
        let mut it = numbers(&text[cuts[i]..cuts[i + 1].max(cuts[i])]);
        while let (Some(u), Some(v), Some(w)) = (it.next(), it.next(), it.next()) {
            b.push(u, v, w);
        }
    })
}

/// Nodes per cluster: a ball of this many nodes fills a few pages of the
/// distance array.
const CLUSTER: usize = 1024;

/// Distance slots come in blocks of `1 << BLOCK` node ids.
const BLOCK: u32 = 6;

/// The new id of every node. Thread i scans its share of the ids for
/// unclaimed roots and grows breadth-first clusters of up to `CLUSTER` nodes
/// from them, seeding the next cluster on the frontier of the last, so
/// consecutive ids are close in the graph. Nodes are claimed atomically;
/// which thread wins a node changes the numbering but never an answer.
fn renumber(g: &Csr, threads: usize) -> Vec<AtomicU32> {
    let n = g.0.len() - 1;
    let rank: Vec<AtomicU32> = (0..n).map(|_| AtomicU32::new(u32::MAX)).collect();
    let claim = |v: usize| rank[v].load(Relaxed) == u32::MAX && rank[v].swap(0, Relaxed) == u32::MAX;
    let lists = parallel(threads, &|i| {
        let mut roots = i * n / threads..(i + 1) * n / threads;
        let (mut mine, mut seed) = (Vec::with_capacity(n / threads * 5 / 4), None);
        while let Some(root) = seed.take().filter(|&v| claim(v)).or_else(|| roots.find(|&v| claim(v))) {
            let start = mine.len();
            mine.push(root as u32);
            let mut next = start;
            'grow: while next < mine.len() {
                for &e in edges(g, mine[next] as usize) {
                    let v = e as u32 as usize;
                    if mine.len() - start == CLUSTER {
                        seed = Some(v);
                        break 'grow;
                    }
                    if claim(v) {
                        mine.push(v as u32);
                    }
                }
                next += 1;
            }
        }
        mine
    });
    let offsets: Vec<usize> = lists.iter().scan(0, |s, l| Some(std::mem::replace(s, *s + l.len()))).collect();
    parallel(threads, &|i| {
        for (k, &v) in lists[i].iter().enumerate() {
            rank[v as usize].store((offsets[i] + k) as u32, Relaxed);
        }
    });
    rank
}

/// The forward and backward graphs of `g`, in the new ids.
fn relabel(g: Csr, rank: &[AtomicU32], threads: usize) -> [Csr; 2] {
    let (n, m) = (rank.len(), g.1.len());
    let span = |i: usize| i * n / threads..(i + 1) * n / threads;
    let r = |v: usize| rank[v].load(Relaxed);
    let fwd = build(n, m, threads, &|i, b| {
        for u in span(i) {
            edges(&g, u).iter().for_each(|&e| b.push(r(u), r(e as u32 as usize), (e >> 32) as u32));
        }
    });
    thread::spawn(move || drop(g)); // unmapping it need not hold anyone up
    let bwd = build(n, m, threads, &|i, b| {
        for u in span(i) {
            edges(&fwd, u).iter().for_each(|&e| b.push(e as u32, u as u32, (e >> 32) as u32));
        }
    });
    [fwd, bwd]
}

/// Per-thread search state, reused between queries. Distances live in
/// blocks of `1 << BLOCK` consecutive node ids, handed out from `pool` as a
/// search first reaches each block (`map` gives a block's offset in `pool`,
/// `owners` lists the blocks in use), so a thread's memory is the footprint
/// of its biggest search rather than a slot for every node. A slot holds the
/// forward and backward tentative distances side by side, as bitwise
/// complements: zero means "not reached".
struct Search {
    map: Vec<u32>,
    pool: Vec<[u64; 2]>,
    owners: Vec<u32>,
    size: [usize; 2],
    heaps: [RadixHeap; 2],
}

impl Search {
    fn slot(&mut self, v: u32) -> usize {
        let block = (v >> BLOCK) as usize;
        if self.map[block] == u32::MAX {
            self.map[block] = (self.owners.len() << BLOCK) as u32;
            self.owners.push(block as u32);
            self.pool.resize(self.pool.len().max(self.owners.len() << BLOCK), [0; 2]);
        }
        self.map[block] as usize | (v as usize & ((1 << BLOCK) - 1))
    }

    /// Lowers `v`'s distance on `side` to `d` if that is shorter; returns its slot.
    fn reach(&mut self, side: usize, v: u32, d: u64) -> usize {
        let i = self.slot(v);
        if d < !self.pool[i][side] {
            self.pool[i][side] = !d;
            self.size[side] += 1;
            self.heaps[side].push(d, v);
        }
        i
    }

    /// Bidirectional Dijkstra: expand the side whose heap holds fewer entries,
    /// keep the best s-t path seen where the two searches meet, and stop once
    /// no shorter one can exist. Balancing by heap size rather than by key
    /// matters when one side is boxed in behind huge weights: that side then
    /// runs dry at once, instead of the other side exploring the whole graph
    /// below the huge key first. Returns `u64::MAX` when `t` is unreachable.
    fn distance(&mut self, graphs: &[Csr; 2], s: u32, t: u32) -> u64 {
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
            if d > !self.pool[i][side] {
                continue; // stale entry
            }
            for &e in edges(&graphs[side], u as usize) {
                let (v, dv) = (e as u32, d + (e >> 32));
                let i = self.reach(side, v, dv);
                // An unreached other side reads as u64::MAX, which saturates.
                best = best.min(dv.saturating_add(!self.pool[i][1 - side]));
            }
        }
        self.pool[..self.owners.len() << BLOCK].fill([0; 2]);
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
    let threads = thread::available_parallelism().map_or(1, |n| n.get());
    let g = load_graph(&format!("{data}/graph.txt"), threads);
    let rank = renumber(&g, threads);
    let graphs = relabel(g, &rank, threads);
    let ids: Vec<u32> = numbers(&fs::read(format!("{data}/queries.txt")).unwrap()).collect();
    let answers: Vec<AtomicI64> = (0..ids.len() / 2).map(|_| AtomicI64::new(0)).collect();
    let next = AtomicUsize::new(0);
    parallel(threads, &|_| {
        let mut search = Search {
            map: vec![u32::MAX; (rank.len() >> BLOCK) + 1],
            pool: Vec::new(),
            owners: Vec::new(),
            size: [0; 2],
            heaps: [(); 2].map(|_| RadixHeap {
                last: 0,
                buckets: std::array::from_fn(|_| Vec::new()),
            }),
        };
        let mut i = next.fetch_add(1, Relaxed);
        while let Some(&[s, t]) = ids.get(2 * i..2 * i + 2) {
            let [s, t] = [s, t].map(|v| rank[v as usize].load(Relaxed));
            // An unreachable target's u64::MAX becomes the -1 the output wants.
            answers[i].store(search.distance(&graphs, s, t) as i64, Relaxed);
            i = next.fetch_add(1, Relaxed);
        }
    });
    let lines = answers.iter().map(|a| format!("{}\n", a.load(Relaxed)));
    fs::write(format!("{out}/distances.txt"), lines.collect::<String>()).unwrap();
}
