import sys
s=open(sys.argv[1]).read(); variant=sys.argv[3]
def rep(a,b):
    global s
    assert s.count(a)==1,a[:60]; s=s.replace(a,b)
A,B,C=[int(x) for x in sys.argv[4:7]]
rep('''/// Calls `f(u, v, w)`''','''/// Asks the CPU to start loading `x[i]` into cache, if `i` is in range.
fn prefetch<T>(x: &[T], i: usize) {
    #[cfg(target_arch = "x86_64")]
    if let Some(p) = x.get(i) {
        unsafe { std::arch::x86_64::_mm_prefetch::<3>(p as *const T as *const i8) };
    }
}

/// Calls `f(u, v, w)`''')
rep('''            'grow: while k < mine.len() {
''','''            'grow: while k < mine.len() {
                // Nodes queued ahead: their row bounds, rows and heads' claims.
                if let Some(&v) = mine.get(k + %d) {
                    prefetch(&g.first, v as usize);
                }
                if let Some(&v) = mine.get(k + %d) {
                    prefetch(&g.adj, g.first[v as usize] as usize);
                }
                if let Some(&v) = mine.get(k + %d) {
                    edges(g, v as usize).iter().for_each(|&e| prefetch(r, (e & ((1 << bits) - 1)) as usize));
                }
''' % (A,B,C))
if variant=='all':
    rep('''        for e in &a[i * m / threads..(i + 1) * m / threads] {
            let old = e.load(Relaxed);''','''        let span = i * m / threads..(i + 1) * m / threads;
        for (j, e) in a[span.clone()].iter().enumerate() {
            if let Some(ahead) = a[span.clone()].get(j + 16) {
                prefetch(&rank, (ahead.load(Relaxed) & mask) as usize);
            }
            let old = e.load(Relaxed);''')
open(sys.argv[2],'w').write(s)
