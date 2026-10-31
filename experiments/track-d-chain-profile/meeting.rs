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

use std::fs::{self, File};
use std::os::unix::fs::FileExt;
use std::sync::atomic::{AtomicU64, AtomicUsize, Ordering::Relaxed};
use std::thread;

const NONE: u64 = u64::MAX;

/// Parses whitespace-separated unsigned decimals. A trailing separator yields
/// one extra 0, which the callers' "take three (or two) at a time" ignores.
fn numbers(s: &[u8]) -> impl Iterator<Item = u32> + '_ {
    s.split(|&b| b <= b' ')
        .map(|t| t.iter().fold(0, |x, &b| x * 10 + (b - b'0') as u32))
}

/// An edge as parsed: (tail, head, weight), or reversed for the backward graph.
type Edge = (u32, u32, u32);

/// Compressed sparse rows: the edges out of `u` are `adj[first[u]..first[u + 1]]`,
/// each packed as `weight << 32 | head`.
struct Csr {
    first: Vec<u32>,
    adj: Vec<u64>,
}

impl Csr {
    /// `(head, weight)` of every edge out of `u`.
    fn edges(&self, u: u32) -> impl Iterator<Item = (u32, u64)> + '_ {
        let range = self.first[u as usize] as usize..self.first[u as usize + 1] as usize;
        self.adj[range].iter().map(|&e| (e as u32, e >> 32))
    }
}

/// Returns the forward graph and the backward graph (every edge reversed).
fn load_graph(path: &str, threads: usize) -> [Csr; 2] {
    let file = File::open(path).unwrap();
    let len = file.metadata().unwrap().len() as usize;
    let mut head = [0u8; 64];
    let got = file.read_at(&mut head, 0).unwrap();
    let mut hdr = numbers(&head[..got]);
    let (n, m) = (hdr.next().unwrap() as usize, hdr.next().unwrap() as usize);
    let block = |u: u32| u as usize * threads / n;

    // Thread i parses the lines whose first byte lies in its byte range and
    // sorts each edge into `buckets[i][dir][block of its tail]`. The ranges
    // start at 1, so thread 0 skips the header the way every other thread
    // skips the partial line it starts in.
    let buckets: Vec<[Vec<Vec<Edge>>; 2]> = thread::scope(|sc| {
        let handles: Vec<_> = (0..threads)
            .map(|i| {
                let file = &file;
                sc.spawn(move || {
                    let start = 1 + i * (len - 1) / threads;
                    let end = 1 + (i + 1) * (len - 1) / threads;
                    let mut buf = vec![0u8; (end + 32).min(len) - (start - 1)];
                    file.read_exact_at(&mut buf, (start - 1) as u64).unwrap();
                    let newline =
                        |from: usize| from + buf[from..].iter().position(|&b| b == b'\n').unwrap();
                    let (from, to) = (newline(0) + 1, newline(end - start));
                    let cap = m / threads / threads * 9 / 8 + 64;
                    let mut out = [0, 1].map(|_| {
                        (0..threads)
                            .map(|_| Vec::with_capacity(cap))
                            .collect::<Vec<_>>()
                    });
                    let mut it = numbers(&buf[from.min(to)..to]);
                    while let (Some(u), Some(v), Some(w)) = (it.next(), it.next(), it.next()) {
                        out[0][block(u)].push((u, v, w));
                        out[1][block(v)].push((v, u, w));
                    }
                    out
                })
            })
            .collect();
        handles.into_iter().map(|h| h.join().unwrap()).collect()
    });
    let (fwd, bwd): (Vec<_>, Vec<_>) = buckets.into_iter().map(|[f, b]| (f, b)).unzip();
    let fwd = build_csr(n, m, threads, fwd); // frees the forward buckets before
    [fwd, build_csr(n, m, threads, bwd)] // the backward graph is allocated
}

/// Thread j owns the nodes of block j and the matching slices of `first` and
/// `adj`, so the counting sort needs no atomics and stays within a cache-sized
/// window of memory.
fn build_csr(n: usize, m: usize, threads: usize, buckets: Vec<Vec<Vec<Edge>>>) -> Csr {
    let mut first = vec![0u32; n + 1];
    let mut adj = vec![0u64; m];
    let (mut first_rest, mut adj_rest) = (&mut first[..n], &mut adj[..]);
    let (buckets, mut base) = (&buckets, 0);
    // Block j is the nodes `u` with `u * threads / n == j`.
    let lo = |j: usize| (j * n).div_ceil(threads);
    thread::scope(|sc| {
        for j in 0..threads {
            let size: usize = buckets.iter().map(|b| b[j].len()).sum();
            let (first, f) = std::mem::take(&mut first_rest).split_at_mut(lo(j + 1) - lo(j));
            let (adj, a) = std::mem::take(&mut adj_rest).split_at_mut(size);
            (first_rest, adj_rest) = (f, a);
            let block_base = base;
            base += size as u32;
            let lo = lo(j);
            sc.spawn(move || {
                let edges = || buckets.iter().flat_map(|b| &b[j]);
                for &(u, _, _) in edges() {
                    first[u as usize - lo] += 1;
                }
                let mut sum = block_base;
                for c in first.iter_mut() {
                    (sum, *c) = (sum + *c, sum);
                }
                let mut cursor = first.to_vec();
                for &(u, v, w) in edges() {
                    let c = &mut cursor[u as usize - lo];
                    adj[(*c - block_base) as usize] = (w as u64) << 32 | v as u64;
                    *c += 1;
                }
            });
        }
    });
    first[n] = m as u32;
    Csr { first, adj }
}

/// Identify non-query vertices having exactly two distinct undirected neighbors.
/// Work comes solely from the runtime graph; direction and parallel edges remain exact.
fn degree2(graphs: [&Csr; 2], queries: &[(u32, u32)], threads: usize) -> Vec<[u32; 2]> {
    let n=graphs[0].first.len()-1;
    let mut pinned=vec![false;n];
    for &(s,t) in queries { pinned[s as usize]=true; pinned[t as usize]=true; }
    let mut info=vec![[u32::MAX;2];n];
    thread::scope(|sc| {
        let mut rest=info.as_mut_slice();
        for j in 0..threads {
            let lo=j*n/threads; let hi=(j+1)*n/threads;
            let (part,r)=std::mem::take(&mut rest).split_at_mut(hi-lo); rest=r;
            let pinned=&pinned;
            sc.spawn(move || {
                for (i,cell) in part.iter_mut().enumerate() {
                    let u=(lo+i) as u32;
                    if pinned[u as usize] { continue; }
                    let mut a=u32::MAX; let mut b=u32::MAX; let mut more=false;
                    for (v,_) in graphs[0].edges(u).chain(graphs[1].edges(u)) {
                        if v==u || v==a || v==b { continue; }
                        if a==u32::MAX { a=v; }
                        else if b==u32::MAX { b=v; }
                        else { more=true; break; }
                    }
                    if !more && b!=u32::MAX { *cell=[a,b]; }
                }
            });
        }
    });
    info
}

/// Replace a core-to-chain edge by the exact directed path to the next core.
/// All chain rows remain available, so missing directions, large weights and
/// long chains safely keep the original edge instead of requiring a fallback graph.
fn shorten(g: Csr, info: &[[u32;2]], threads:usize) -> Csr {
    let n=info.len();
    let mut output=vec![0u64;g.adj.len()];
    thread::scope(|sc| {
        let mut rest=output.as_mut_slice();
        for j in 0..threads {
            let lo=j*n/threads; let hi=(j+1)*n/threads;
            let start=g.first[lo] as usize; let end=g.first[hi] as usize;
            let (out,r)=std::mem::take(&mut rest).split_at_mut(end-start); rest=r;
            let g=&g;
            sc.spawn(move || {
                for u in lo..hi {
                    let a=g.first[u] as usize; let b=g.first[u+1] as usize;
                    for at in a..b {
                        let original=g.adj[at];
                        let mut value=original;
                        if info[u][0]==u32::MAX {
                            let (mut prev,mut v)=(u as u32,original as u32);
                            let mut w=original >> 32; let mut steps=0;
                            while info[v as usize][0]!=u32::MAX && steps<16 {
                                let [a,b]=info[v as usize];
                                let next=if a==prev { b } else if b==prev { a } else { break; };
                                let edge=g.edges(v).filter(|&(x,_)| x==next).map(|(_,w)|w).min();
                                let Some(edge)=edge else { break; };
                                let sum=w+edge;
                                if sum>u32::MAX as u64 { break; }
                                prev=v; v=next; w=sum; steps+=1;
                            }
                            // Only commit a shortcut if a core endpoint was reached.
                            if steps>0 && info[v as usize][0]==u32::MAX { value=(w<<32)|v as u64; }
                        }
                        out[at-start]=value;
                    }
                }
            });
        }
    });
    Csr { first:g.first, adj:output }
}

/// Per-thread search state, reused between queries. `dist[v]` holds the
/// forward and backward tentative distances of `v` side by side (one cache
/// line), as bitwise complements: zeroed memory means "not reached", so the
/// array costs nothing until a search touches it.
#[derive(Default)]
struct Stat { tries:u64, improved:u64, popped:u64, stale:u64, cleared:u64 }
struct Search {
    stat: Stat,
    dist: Vec<[u64; 2]>,
    touched: Vec<u32>,
    heaps: [RadixHeap; 2],
}

impl Search {
    fn new(n: usize) -> Self {
        Search {
            stat: Stat::default(),
            dist: vec![[0; 2]; n],
            touched: Vec::new(),
            heaps: Default::default(),
        }
    }

    fn reach(&mut self, side: usize, v: u32, d: u64) -> bool {
        self.stat.tries += 1;
        let slot = &mut self.dist[v as usize];
        if d < !slot[side] {
            self.stat.improved += 1;
            if *slot == [0; 2] {
                self.touched.push(v);
            }
            slot[side] = !d;
            self.heaps[side].push(d, v);
            return true;
        }
        false
    }

    /// Bidirectional Dijkstra: expand the side with the smaller key, keep the
    /// best s-t path seen where the two searches meet, and stop once no shorter
    /// one can exist. A dead end on either side (no out-edges from `s`, no
    /// in-edges into `t`) empties its heap at once, so those pairs are cheap.
    fn distance(&mut self, graphs: [&Csr; 2], s: u32, t: u32) -> u64 {
        if s == t {
            return 0;
        }
        self.reach(0, s, 0);
        self.reach(1, t, 0);
        let mut best = NONE;
        while let (Some(a), Some(b)) = (self.heaps[0].top(), self.heaps[1].top()) {
            if a.saturating_add(b) >= best {
                break;
            }
            let side = match self.heaps[0].count.cmp(&self.heaps[1].count) {
                std::cmp::Ordering::Less => 0,
                std::cmp::Ordering::Greater => 1,
                std::cmp::Ordering::Equal => (a > b) as usize,
            };
            let (d, u) = self.heaps[side].pop();
            self.stat.popped += 1;
            if d > !self.dist[u as usize][side] {
                self.stat.stale += 1;
                continue; // stale entry
            }
            for (v, w) in graphs[side].edges(u) {
                if self.reach(side, v, d + w) {
                    let other = self.dist[v as usize][1 - side];
                    if other != 0 {
                        best = best.min(d + w + !other);
                    }
                }
            }
        }
        self.stat.cleared += self.touched.len() as u64;
        for &v in &self.touched {
            self.dist[v as usize] = [0; 2];
        }
        self.touched.clear();
        self.heaps.iter_mut().for_each(RadixHeap::clear);
        best
    }
}

fn main() {
    let total=std::time::Instant::now();
    let dir = |key, default: &str| std::env::var(key).unwrap_or(default.to_string());
    let (data, out) = (dir("SD_DATA", "/data"), dir("SD_OUT", "/out"));
    let threads = thread::available_parallelism().map_or(1, |n| n.get());
    let [fwd, bwd] = load_graph(&format!("{data}/graph.txt"), threads);
    eprintln!("STAGE graph {:.9}",total.elapsed().as_secs_f64());
    let text = fs::read(format!("{data}/queries.txt")).unwrap();
    let mut it = numbers(&text);
    let mut queries = Vec::new();
    while let (Some(s), Some(t)) = (it.next(), it.next()) {
        queries.push((s, t));
    }

    let info=degree2([&fwd,&bwd], &queries, threads);
    eprintln!("STAGE degree {:.9}",total.elapsed().as_secs_f64());
    let fwd=shorten(fwd,&info,threads);
    eprintln!("STAGE fwd {:.9}",total.elapsed().as_secs_f64());
    let bwd=shorten(bwd,&info,threads);
    eprintln!("STAGE bwd {:.9}",total.elapsed().as_secs_f64());
    let query_start=std::time::Instant::now();
    let answers: Vec<AtomicU64> = queries.iter().map(|_| AtomicU64::new(0)).collect();
    let next = AtomicUsize::new(0);
    thread::scope(|sc| {
        for _ in 0..threads {
            sc.spawn(|| {
                let mut search = Search::new(fwd.first.len() - 1);
                loop {
                    let i = next.fetch_add(1, Relaxed);
                    let Some(&(s, t)) = queries.get(i) else { break };
                    answers[i].store(search.distance([&fwd, &bwd], s, t), Relaxed);
                }
                let z=&search.stat; eprintln!("STAT {} {} {} {} {}",z.tries,z.improved,z.popped,z.stale,z.cleared);
            });
        }
    });
    eprintln!("STAGE query {:.9} total {:.9}",query_start.elapsed().as_secs_f64(),total.elapsed().as_secs_f64());
    let text: String = answers
        .into_iter()
        .map(|a| match a.into_inner() {
            NONE => "-1\n".to_string(),
            d => format!("{d}\n"),
        })
        .collect();
    fs::write(format!("{out}/distances.txt"), text).unwrap();
}

/// Monotone priority queue: keys pushed are never below the last key popped.
/// Bucket i holds keys whose highest bit differing from `last` is bit i - 1.
struct RadixHeap {
    last: u64,
    buckets: [Vec<(u64, u32)>; 65],
    count: usize,
}

impl Default for RadixHeap {
    fn default() -> Self {
        RadixHeap {
            last: 0,
            buckets: std::array::from_fn(|_| Vec::new()),
            count: 0,
        }
    }
}

impl RadixHeap {
    fn slot(&self, k: u64) -> usize {
        64 - (k ^ self.last).leading_zeros() as usize
    }
    fn push(&mut self, k: u64, v: u32) {
        let i = self.slot(k);
        self.buckets[i].push((k, v));
        self.count += 1;
    }
    /// The smallest key, after moving every entry with that key into bucket 0.
    fn top(&mut self) -> Option<u64> {
        if self.buckets[0].is_empty() {
            let i = self.buckets.iter().position(|b| !b.is_empty())?;
            let mut b = std::mem::take(&mut self.buckets[i]);
            self.count -= b.len();
            self.last = b.iter().map(|e| e.0).min().unwrap();
            for e in b.drain(..) {
                self.push(e.0, e.1);
            }
            self.buckets[i] = b;
        }
        Some(self.last)
    }
    /// Call only after `top` returned `Some`.
    fn pop(&mut self) -> (u64, u32) {
        self.count -= 1;
        self.buckets[0].pop().unwrap()
    }
    fn clear(&mut self) {
        self.last = 0;
        self.count = 0;
        self.buckets.iter_mut().for_each(Vec::clear);
    }
}
