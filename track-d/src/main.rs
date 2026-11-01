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

use std::sync::atomic::{AtomicI64, AtomicU32, AtomicU64, AtomicUsize, Ordering::Relaxed};
use std::{fs, fs::File, mem::take, os::fd::AsRawFd, thread};

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

/// Asks the CPU to start loading `x[i]` into cache, if `i` is in range.
fn prefetch<T>(x: &[T], i: usize) {
    #[cfg(target_arch = "x86_64")]
    if let Some(p) = x.get(i) {
        unsafe { std::arch::x86_64::_mm_prefetch::<3>(p as *const T as *const i8) };
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
    let line_end = |p: usize| (p..len).find(|&i| text[i] == b'\n').map_or(len, |i| i + 1);
    let mut p = 0;
    let (n, m) = (num(text, &mut p) as usize, num(text, &mut p) as usize);
    let bits = 32 - (n as u32).leading_zeros();
    let wide = u32::MAX >> bits;
    let cut = |i: usize| line_end((i * len / threads).max(1) - 1);
    let block_len = n.div_ceil(threads);
    let parts = parallel(threads, &|i| {
        // Sized for an even spread, so the lists rarely have to grow.
        let cap = m / threads / threads * 9 / 8 + 64;
        let mut lists: Vec<Vec<u64>> = (0..threads).map(|_| Vec::with_capacity(cap)).collect();
        let mut big = Vec::new();
        let (mut p, end) = (cut(i), cut(i + 1));
        while p < end {
            let (u, v, w) = (num(text, &mut p), num(text, &mut p), num(text, &mut p));
            lists[u as usize / block_len].push((u as u64) << 32 | (v | w.min(wide) << bits) as u64);
            if w >= wide {
                big.push((u, v, w));
            }
        }
        (lists, big)
    });
    let (mut buckets, big): (Vec<_>, Vec<_>) = parts.into_iter().unzip();
    let (mut first, mut adj) = (zeros(n + 1), zeros(m));
    let (mut adj_rest, mut start) = (&mut adj[..], 0);
    thread::scope(|sc| {
        for (j, first) in first[..n].chunks_mut(block_len).enumerate() {
            let col: Vec<_> = buckets.iter_mut().map(|b| take(&mut b[j])).collect();
            let size: usize = col.iter().map(Vec::len).sum();
            let (adj, rest) = take(&mut adj_rest).split_at_mut(size);
            let at = move |e: u64| (e >> 32) as usize - j * block_len;
            adj_rest = rest;
            sc.spawn(move || {
                col.iter().flatten().for_each(|&e| first[at(e)] += 1);
                first.iter_mut().fold(start, |sum, c| {
                    *c += sum;
                    *c
                });
                for list in col {
                    for e in list {
                        let c = &mut first[at(e)];
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

/// Distance slots come in blocks of `1 << BLOCK` node ids; a block number in
/// use fits a u16 as long as n < 2^22 (the spec fixes n at 1,740,512).
const BLOCK: u32 = 6;

/// Search queues order nodes by `distance >> SHIFT`, not by exact distance:
/// coarser keys mean far fewer radix-heap redistributions.
const SHIFT: u32 = 6;

/// The new id of every node (stored complemented: zero is "unclaimed"),
/// and the forward graph with its rows in the new order but heads still in
/// the file's ids. Thread i scans its share of the ids for unclaimed roots
/// and grows breadth-first clusters of up to `CLUSTER` nodes from them,
/// seeding the next cluster on the frontier of the last; each finished
/// cluster takes the next free run of ids and of edge slots (one atomic add
/// for both, so the two runs line up) and copies its rows there while they
/// are still in cache. Nodes are claimed atomically; which thread wins a
/// node changes the numbering but never an answer.
fn renumber(g: &Csr, bits: u32, threads: usize) -> (Vec<u32>, Csr) {
    let (n, m) = (g.first.len() - 1, g.adj.len());
    let (mut rank, mut first, mut adj) = (vec![0; n], zeros(n + 1), zeros(m));
    let (r, f, a) = (atomic(&mut rank), atomic(&mut first), atomic(&mut adj));
    // Unclaimed is 0; a claimed node holds 1 or its complemented id, never 0,
    // so raising a slot to at least 1 claims it only if it was free.
    let claim = |&v: &usize| r[v].load(Relaxed) == 0 && r[v].fetch_max(1, Relaxed) == 0;
    let next = AtomicU64::new(0);
    parallel(threads, &|i| {
        let mut roots = i * n / threads..(i + 1) * n / threads;
        let (mut mine, mut seed) = (Vec::with_capacity(CLUSTER), None);
        while let Some(root) = seed.take().filter(claim).or_else(|| roots.find(claim)) {
            mine.push(root as u32);
            let mut k = 0;
            'grow: while k < mine.len() {
                // A node queued ahead: start loading its row.
                if let Some(&v) = mine.get(k + 8) {
                    prefetch(&g.adj, g.first[v as usize] as usize);
                }
                for &e in edges(g, mine[k] as usize) {
                    let v = (e & ((1 << bits) - 1)) as usize;
                    if mine.len() == CLUSTER {
                        seed = Some(v);
                        break 'grow;
                    }
                    if claim(&v) {
                        mine.push(v as u32);
                    }
                }
                k += 1;
            }
            // The cluster is complete: number it and move its rows.
            let size: usize = mine.iter().map(|&v| edges(g, v as usize).len()).sum();
            let base = next.fetch_add((mine.len() as u64) << 32 | size as u64, Relaxed);
            let (id, mut p) = ((base >> 32) as usize, base as u32);
            for (k, v) in mine.drain(..).enumerate() {
                r[v as usize].store(!((id + k) as u32), Relaxed);
                f[id + k].store(p, Relaxed);
                for &e in edges(g, v as usize) {
                    a[p as usize].store(e, Relaxed);
                    p += 1;
                }
            }
        }
    });
    first[n] = m as u32;
    (rank, Csr { first, adj })
}

/// The forward and backward graphs in the new ids. Thread i owns the heads
/// in `span(i)`: their in-edge counts and backward rows. It renames the heads
/// of its own tails' edges and counts those that land in its own span; an
/// edge landing in another span (about 7% after renumbering) is handed to
/// that span's owner in a list. So every counter and row has one writer, and
/// no atomic read-modify-write is needed.
fn relabel(mut fwd: Csr, rank: Vec<u32>, bits: u32, threads: usize) -> [Csr; 2] {
    let (n, m, mask) = (rank.len(), fwd.adj.len(), (1 << bits) - 1);
    let len = n.div_ceil(threads);
    let span = |i: usize| i * len..((i + 1) * len).min(n);
    let (mut first, mut adj) = (zeros(n + 1), zeros(m));
    let (f, a, b) = (atomic(&mut first), atomic(&mut fwd.adj), atomic(&mut adj));
    let bump = |v: u32| f[v as usize].store(f[v as usize].load(Relaxed) + 1, Relaxed);
    let away = parallel(threads, &|i| {
        let mut away = vec![Vec::new(); threads];
        for u in span(i) {
            for e in &a[fwd.first[u] as usize..fwd.first[u + 1] as usize] {
                let old = e.load(Relaxed);
                let head = !rank[(old & mask) as usize];
                e.store(head | old & !mask, Relaxed);
                match head as usize / len {
                    j if j == i => bump(head),
                    j => away[j].push((head, u as u32 | old & !mask)),
                }
            }
        }
        away
    });
    drop(rank);
    let theirs = |j: usize| away.iter().flat_map(move |l| &l[j]);
    // Each owner adds the handed-over edges to its counts, then turns them
    // into running sums from the end of the spans before it.
    let sizes = parallel(threads, &|j| {
        theirs(j).for_each(|&(v, _)| bump(v));
        span(j).map(|v| f[v].load(Relaxed)).sum::<u32>()
    });
    let place = |v: usize, x: u32| {
        let p = f[v].load(Relaxed) - 1;
        f[v].store(p, Relaxed);
        b[p as usize].store(x, Relaxed);
    };
    parallel(threads, &|j| {
        span(j).fold(sizes[..j].iter().sum(), |sum: u32, v| {
            f[v].store(sum + f[v].load(Relaxed), Relaxed);
            f[v].load(Relaxed)
        });
        for u in span(j) {
            for &e in edges(&fwd, u) {
                if (e & mask) as usize / len == j {
                    place((e & mask) as usize, u as u32 | e & !mask);
                }
            }
        }
        theirs(j).for_each(|&(v, x)| place(v as usize, x));
    });
    first[n] = m as u32;
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

/// One side (forward or backward) of a thread's search state, reused between
/// queries. Distances live in blocks of `1 << BLOCK` consecutive node ids,
/// handed out from `pool` as the side first reaches each block (`map` gives a
/// block's offset in `pool`, `owners` lists the blocks in use), so a thread's
/// memory is the footprint of its biggest search rather than a slot for every
/// node; the two sides keep separate pools, as their balls barely overlap.
/// A distance is stored as its bitwise complement: zero means "not reached".
struct Side<D> {
    map: Vec<u16>,
    pool: Vec<D>,
    owners: Vec<u32>,
    heap: RadixHeap,
    /// Entries in `heap`, stale ones included.
    size: usize,
    /// Whether this side refused a distance too long for `D`.
    cut: bool,
}

impl<D: Dist> Side<D> {
    fn new(n: usize) -> Self {
        let (last, buckets) = (0, std::array::from_fn(|_| Vec::new()));
        Side {
            map: vec![u16::MAX; (n >> BLOCK) + 1],
            pool: Vec::new(),
            owners: Vec::new(),
            heap: RadixHeap { last, buckets },
            size: 0,
            cut: false,
        }
    }

    /// `v`'s tentative distance, or `u64::MAX` if not reached.
    #[inline(always)]
    fn get(&self, v: u32) -> u64 {
        match self.map[(v >> BLOCK) as usize] {
            u16::MAX => u64::MAX,
            at => self.pool[(at as usize) << BLOCK | (v as usize & ((1 << BLOCK) - 1))].get(),
        }
    }

    /// Lowers `v`'s distance to `d` if that is shorter; says whether it did.
    #[inline(always)]
    fn reach(&mut self, v: u32, d: u64) -> bool {
        let block = (v >> BLOCK) as usize;
        if self.map[block] == u16::MAX {
            self.map[block] = self.owners.len() as u16;
            self.owners.push(block as u32);
            let end = self.owners.len() << BLOCK;
            self.pool.resize(self.pool.len().max(end), D::default());
        }
        let i = (self.map[block] as usize) << BLOCK | (v as usize & ((1 << BLOCK) - 1));
        if d >= self.pool[i].get() {
            return false;
        }
        let Some(x) = D::put(d) else {
            self.cut = true;
            return false;
        };
        (self.pool[i], self.size) = (x, self.size + 1);
        self.heap.push(d >> SHIFT, v);
        true
    }

    fn clear(&mut self) {
        self.pool[..self.owners.len() << BLOCK].fill(D::default());
        for block in self.owners.drain(..) {
            self.map[block as usize] = u16::MAX;
        }
        self.heap.buckets.iter_mut().for_each(Vec::clear);
        (self.heap.last, self.size, self.cut) = (0, 0, false);
    }
}

/// Bidirectional Dijkstra: expand the side whose heap holds fewer entries,
/// keep the best s-t path seen where the two searches meet, and stop once
/// no shorter one can exist. Balancing by heap size rather than by key
/// matters when one side is boxed in behind huge weights: that side then
/// runs dry at once, instead of the other side exploring the whole graph
/// below the huge key first. Returns `u64::MAX` when `t` is unreachable, and
/// whether a distance was refused.
///
/// The queues are keyed by `distance >> SHIFT`, so nodes in one bucket come
/// out in any order and a node can improve after it was expanded. Every
/// improvement is queued again, in the current bucket or a later one, and
/// expanded with its new distance. A bucket's start is a lower bound on any
/// distance still to be expanded on that side, so once the two starts add
/// up to `best`, no shorter path remains: its first unexpanded node on each
/// side would still be queued at or above that side's start.
fn distance<D: Dist>(sides: &mut [Side<D>; 2], net: &Net, s: u32, t: u32) -> (u64, bool) {
    let (mask, wide) = ((1 << net.bits) - 1, u32::MAX >> net.bits);
    sides[0].reach(s, 0);
    sides[1].reach(t, 0);
    let mut best = if s == t { 0 } else { u64::MAX };
    while let (Some(a), Some(b)) = (sides[0].heap.top(), sides[1].heap.top()) {
        if (a + b).saturating_mul(1 << SHIFT) >= best {
            break;
        }
        let side = (sides[0].size > sides[1].size) as usize;
        let [x, y] = &mut *sides;
        let (me, other) = if side == 0 { (x, &*y) } else { (y, &*x) };
        let (key, u) = ([a, b][side], me.heap.buckets[0].pop().unwrap().1);
        me.size -= 1;
        // The next two nodes this side pops: start loading their rows.
        let q = &me.heap.buckets[0];
        if let Some(&(_, next)) = q.len().checked_sub(2).map(|i| &q[i]) {
            prefetch(&net.graphs[side].first, next as usize);
        }
        if let Some(&(_, next)) = q.last() {
            let g = &net.graphs[side];
            prefetch(&g.adj, g.first[next as usize] as usize);
        }
        let d = me.get(u);
        if d >> SHIFT < key {
            continue; // stale: already expanded from an earlier bucket
        }
        for &e in edges(&net.graphs[side], u as usize) {
            let (v, mut w) = (e & mask, e >> net.bits);
            if w == wide {
                let key = [(u as u64) << 32 | v as u64, (v as u64) << 32 | u as u64][side];
                w = net.wide[net.wide.binary_search_by_key(&key, |x| x.0).unwrap()].1;
            }
            // Only an improvement can make a shorter meeting; an unreached
            // other side reads as u64::MAX, which saturates.
            if me.reach(v, d + w as u64) {
                best = best.min((d + w as u64).saturating_add(other.get(v)));
            }
        }
    }
    let cut = sides[0].cut || sides[1].cut;
    sides.iter_mut().for_each(Side::clear);
    (best, cut)
}

/// Monotone priority queue: keys pushed are never below the last key popped.
/// Bucket i holds keys whose highest bit differing from `last` is bit i - 1.
/// Dijkstra only pushes keys below `last + 2^32` (one edge past it), so an
/// entry keeps just the key's low 32 bits and the rest comes from `last`.
struct RadixHeap {
    last: u64,
    buckets: [Vec<(u32, u32)>; 65],
}

impl RadixHeap {
    fn push(&mut self, k: u64, v: u32) {
        self.buckets[64 - (k ^ self.last).leading_zeros() as usize].push((k as u32, v));
    }

    /// The smallest key, after moving every entry with that key into bucket 0.
    fn top(&mut self) -> Option<u64> {
        if self.buckets[0].is_empty() {
            let i = self.buckets.iter().position(|b| !b.is_empty())?;
            let (mut b, old) = (std::mem::take(&mut self.buckets[i]), self.last);
            let key = |k: u32| old + k.wrapping_sub(old as u32) as u64;
            self.last = b.iter().map(|e| key(e.0)).min().unwrap();
            b.drain(..).for_each(|(k, v)| self.push(key(k), v));
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
    let (g, bits, big) = load_graph(&format!("{data}/graph.txt"), threads);
    let (rank, fwd) = renumber(&g, bits, threads);
    drop(g);
    let r = |v: u32| !rank[v as usize];
    let (text, mut p, mut ids) = (fs::read(format!("{data}/queries.txt")).unwrap(), 0, vec![]);
    while p < text.len() {
        ids.push(r(num(&text, &mut p)));
    }
    let key = |u, v| (r(u) as u64) << 32 | r(v) as u64;
    let mut wide: Vec<_> = big.iter().map(|&(u, v, w)| (key(u, v), w)).collect();
    wide.sort_unstable();
    wide.dedup_by_key(|x| x.0);
    let n = rank.len();
    let graphs = relabel(fwd, rank, bits, threads);
    let net = Net { graphs, bits, wide };
    let answers: Vec<AtomicI64> = (0..ids.len() / 2).map(|_| AtomicI64::new(0)).collect();
    let next = AtomicUsize::new(0);
    parallel(threads, &|_| {
        let (mut narrow, mut wide) = ([0; 2].map(|_| Side::<u32>::new(n)), None);
        let mut i = next.fetch_add(1, Relaxed);
        while let Some(&[s, t]) = ids.get(2 * i..2 * i + 2) {
            let (mut d, cut) = distance(&mut narrow, &net, s, t);
            if cut && d >= u32::MAX as u64 {
                let wide = wide.get_or_insert_with(|| [0; 2].map(|_| Side::<u64>::new(n)));
                d = distance(wide, &net, s, t).0;
            }
            // An unreachable target's u64::MAX becomes the -1 the output wants.
            answers[i].store(d as i64, Relaxed);
            i = next.fetch_add(1, Relaxed);
        }
    });
    let lines = answers.iter().map(|a| format!("{}\n", a.load(Relaxed)));
    fs::write(format!("{out}/distances.txt"), lines.collect::<String>()).unwrap();
    std::process::exit(0); // the kernel frees everything at once
}
