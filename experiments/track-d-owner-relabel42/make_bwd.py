import sys
s=open(sys.argv[1]).read(); opts=sys.argv[3].split(',')
def rep(a,b):
    global s
    assert s.count(a)==1,(s.count(a),a[:70]); s=s.replace(a,b)
if 'seqsum' in opts:
    i=s.index('/// Turns per-node counts into running sums'); j=s.index('/// The forward graph in the file')
    s=s[:i]+s[j:]
    rep('''    drop(rank);
    ends(f, threads);''','''    drop(rank);
    // Running sums: first[u] becomes the end of u's in-edges, and the
    // scatter below places each edge by taking one off its head's end.
    let mut sum = 0;
    for c in f {
        sum += c.load(Relaxed);
        c.store(sum, Relaxed);
    }''')
if 'loops' in opts:
    rep('''    let mine = |i: usize| span(i).flat_map(|u| edges(&fwd, u).iter().map(move |&e| (u as u32, e)));
    let a = atomic(&mut adj);
    parallel(threads, &|i| {
        for (u, e) in mine(i) {
            let p = f[(e & mask) as usize].fetch_sub(1, Relaxed) - 1;
            a[p as usize].store(u | e & !mask, Relaxed);
        }
    });''','''    let a = atomic(&mut adj);
    parallel(threads, &|i| {
        for u in span(i) {
            for &e in edges(&fwd, u) {
                let p = f[(e & mask) as usize].fetch_sub(1, Relaxed) - 1;
                a[p as usize].store(u as u32 | e & !mask, Relaxed);
            }
        }
    });''')
open(sys.argv[2],'w').write(s)
