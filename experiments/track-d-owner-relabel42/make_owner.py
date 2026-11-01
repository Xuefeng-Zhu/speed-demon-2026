import sys
s=open(sys.argv[1]).read()
def rep(a,b):
    global s
    assert s.count(a)==1,(s.count(a),a[:70]); s=s.replace(a,b)
i=s.index('/// Turns per-node counts into running sums'); j=s.index('/// The forward graph in the file')
s=s[:i]+s[j:]
i=s.index('/// The forward and backward graphs in the new ids'); j=s.index('/// A tentative distance as stored')
s=s[:i]+'''/// The forward and backward graphs in the new ids. Thread i owns the heads
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
                    j => away[j].push((head as u64) << 32 | (u as u32 | old & !mask) as u64),
                }
            }
        }
        away
    });
    drop(rank);
    let theirs = |j: usize| away.iter().flat_map(move |l| &l[j]);
    parallel(threads, &|j| theirs(j).for_each(|&x| bump((x >> 32) as u32)));
    // Running sums: first[v] becomes the end of v's in-edges, and each edge
    // is then placed by taking one off its head's end.
    let mut sum = 0;
    for c in f {
        sum += c.load(Relaxed);
        c.store(sum, Relaxed);
    }
    let place = |v: usize, x: u32| {
        let p = f[v].load(Relaxed) - 1;
        f[v].store(p, Relaxed);
        b[p as usize].store(x, Relaxed);
    };
    parallel(threads, &|j| {
        for u in span(j) {
            for e in &a[fwd.first[u] as usize..fwd.first[u + 1] as usize] {
                let e = e.load(Relaxed);
                if (e & mask) as usize / len == j {
                    place((e & mask) as usize, u as u32 | e & !mask);
                }
            }
        }
        theirs(j).for_each(|&x| place((x >> 32) as usize, x as u32));
    });
    [fwd, Csr { first, adj }]
}

'''+s[j:]
open(sys.argv[2],'w').write(s)
