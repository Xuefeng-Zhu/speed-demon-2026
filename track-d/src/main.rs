//! Speed Demon 2026, Track D (Traverse): exact shortest paths on a 5M-edge graph.
//!
//! 1. Every thread reads and parses its own slice of `graph.txt` (positioned
//!    reads, no shared buffer) and buckets each edge, and its reverse, by
//!    the block of node ids its tail falls in.
//! 2. Thread j turns block j into its slice of the forward and backward CSR
//!    arrays with a counting sort; each edge becomes one `u64`.
//! 3. Threads pull queries from a shared counter and answer each with a
//!    bidirectional Dijkstra search. Its distance arrays are reused between
//!    queries and only the touched entries are cleared.
//!
//! Std only. Override the directories with `SD_DATA` and `SD_OUT`.

use std::sync::atomic::{AtomicI64, AtomicUsize, Ordering::Relaxed};
use std::{fs, fs::File, os::unix::fs::FileExt, thread};

/// Parses whitespace-separated unsigned decimals. A trailing separator (or
/// zero byte) yields one extra 0, which "take three (or two) at a time" ignores.
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

/// One parsing thread's edges as (tail, head, weight), by block of the tail.
type Buckets = Vec<Vec<(u32, u32, u32)>>;

/// Returns the forward graph and the backward graph (every edge reversed).
fn load_graph(path: &str, threads: usize) -> [Csr; 2] {
    let file = File::open(path).unwrap();
    let len = file.metadata().unwrap().len() as usize;
    let mut head = [0u8; 64]; // the unread tail of a short file stays 0, a separator
    file.read_at(&mut head, 0).unwrap();
    let header: Vec<usize> = numbers(&head).take(2).map(|x| x as usize).collect();
    let (n, m) = (header[0], header[1]);
    let block_len = n.div_ceil(threads);
    let block = |u: u32| u as usize / block_len;

    // Thread i parses the lines whose first byte lies in its byte range and
    // sorts each edge into `parsed[i][dir][block of its tail]`. The ranges
    // start at 1, so thread 0 skips the header the way every other thread
    // skips the partial line it starts in.
    let parsed = parallel(threads, &|i| {
        let [start, end] = [i, i + 1].map(|i| 1 + i * (len - 1) / threads);
        let mut buf = vec![0u8; (end + 32).min(len) - (start - 1)];
        file.read_exact_at(&mut buf, (start - 1) as u64).unwrap();
        let newline = |from: usize| from + buf[from..].iter().position(|&b| b == b'\n').unwrap();
        let (from, to) = (newline(0) + 1, newline(end - start));
        // Sized for an even spread, so the buckets rarely have to grow.
        let bucket = || Vec::with_capacity(m / threads / threads * 9 / 8 + 64);
        let mut out: [Buckets; 2] = [(); 2].map(|_| (0..threads).map(|_| bucket()).collect());
        let mut it = numbers(&buf[from.min(to)..to]);
        while let (Some(u), Some(v), Some(w)) = (it.next(), it.next(), it.next()) {
            out[0][block(u)].push((u, v, w));
            out[1][block(v)].push((v, u, w));
        }
        out
    });
    let (fwd, bwd): (Vec<_>, Vec<_>) = parsed.into_iter().map(|[f, b]| (f, b)).unzip();
    // One direction at a time, so the forward buckets are freed before the
    // backward graph is allocated.
    [fwd, bwd].map(|buckets| build_csr(n, m, block_len, &buckets))
}

/// Block j is the `block_len` nodes from `j * block_len` on. Thread j owns
/// block j and the matching slices of `first` and `adj` (the latter starting
/// at edge `start`), so the counting sort needs no atomics and stays within a
/// cache-sized window of memory.
fn build_csr(n: usize, m: usize, block_len: usize, buckets: &[Buckets]) -> Csr {
    let (mut first, mut adj) = (vec![0u32; n + 1], vec![0u64; m]);
    let (mut adj_rest, mut start) = (&mut adj[..], 0);
    thread::scope(|sc| {
        for (j, first) in first[..n].chunks_mut(block_len).enumerate() {
            let size: usize = buckets.iter().map(|b| b[j].len()).sum();
            let (adj, rest) = std::mem::take(&mut adj_rest).split_at_mut(size);
            let lo = j * block_len;
            adj_rest = rest;
            sc.spawn(move || {
                let edges = || buckets.iter().flat_map(|b| &b[j]);
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

/// Per-thread search state, reused between queries. `dist[v]` holds the
/// forward and backward tentative distances of `v` side by side (one cache
/// line), as bitwise complements: zeroed memory means "not reached", so the
/// array costs nothing until a search touches it.
struct Search {
    dist: Vec<[u64; 2]>,
    touched: Vec<u32>,
    heaps: [RadixHeap; 2],
}

impl Search {
    fn reach(&mut self, side: usize, v: u32, d: u64) {
        let slot = &mut self.dist[v as usize];
        if d < !slot[side] {
            slot[side] = !d;
            self.touched.push(v); // may repeat v, which the reset tolerates
            self.heaps[side].push(d, v);
        }
    }

    /// Bidirectional Dijkstra: expand the side with the smaller key, keep the
    /// best s-t path seen where the two searches meet, and stop once no shorter
    /// one can exist. A dead end on either side (no out-edges from `s`, no
    /// in-edges into `t`) empties its heap at once, so those pairs are cheap.
    /// Returns `u64::MAX` when `t` is unreachable.
    fn distance(&mut self, graphs: &[Csr; 2], s: u32, t: u32) -> u64 {
        self.reach(0, s, 0);
        self.reach(1, t, 0);
        let mut best = if s == t { 0 } else { u64::MAX };
        while let (Some(a), Some(b)) = (self.heaps[0].top(), self.heaps[1].top()) {
            if a.saturating_add(b) >= best {
                break;
            }
            let side = (a > b) as usize;
            let (d, u) = self.heaps[side].buckets[0].pop().unwrap();
            if d > !self.dist[u as usize][side] {
                continue; // stale entry
            }
            let (first, adj) = &graphs[side];
            for &e in &adj[first[u as usize] as usize..first[u as usize + 1] as usize] {
                let (v, dv) = (e as u32, d + (e >> 32));
                self.reach(side, v, dv);
                // An unreached other side reads as u64::MAX, which saturates.
                best = best.min(dv.saturating_add(!self.dist[v as usize][1 - side]));
            }
        }
        for v in self.touched.drain(..) {
            self.dist[v as usize] = [0; 2];
        }
        // A stale `last` is harmless: the next search's first `top` sees one
        // entry per heap and resets `last` to its key.
        for heap in &mut self.heaps {
            heap.buckets.iter_mut().for_each(Vec::clear);
        }
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
    let threads = thread::available_parallelism().map_or(1, |n| n.get());
    let graphs = load_graph(&format!("{data}/graph.txt"), threads);
    let ids: Vec<u32> = numbers(&fs::read(format!("{data}/queries.txt")).unwrap()).collect();
    let answers: Vec<AtomicI64> = (0..ids.len() / 2).map(|_| AtomicI64::new(0)).collect();
    let next = AtomicUsize::new(0);
    parallel(threads, &|_| {
        let mut search = Search {
            dist: vec![[0; 2]; graphs[0].0.len() - 1],
            touched: Vec::new(),
            heaps: [(); 2].map(|_| RadixHeap {
                last: 0,
                buckets: std::array::from_fn(|_| Vec::new()),
            }),
        };
        let mut i = next.fetch_add(1, Relaxed);
        while let Some(&[s, t]) = ids.get(2 * i..2 * i + 2) {
            // An unreachable target's u64::MAX becomes the -1 the output wants.
            answers[i].store(search.distance(&graphs, s, t) as i64, Relaxed);
            i = next.fetch_add(1, Relaxed);
        }
    });
    let lines = answers.iter().map(|a| format!("{}\n", a.load(Relaxed)));
    fs::write(format!("{out}/distances.txt"), lines.collect::<String>()).unwrap();
}
