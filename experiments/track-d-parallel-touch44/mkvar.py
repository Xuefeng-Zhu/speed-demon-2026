import sys
# mkvar.py SRC DST VARIANTS: Track D candidate edits. VARIANTS is a comma list of z, p<N>, d.
#   z    zeros() first-touches its huge pages from `threads` threads (one writer per page)
#   p<N> relabel's first pass prefetches the rank entry of the edge N ahead
#   d    the parse's bucket index uses a 128-bit multiply instead of a division
src, dst, vs = sys.argv[1], sys.argv[2], sys.argv[3].split(',')
s = open(src).read()
def rep(a, b, cnt=1):
    global s
    assert s.count(a) >= cnt, a
    s = s.replace(a, b, cnt)
for v in vs:
    if v == 'z':
        rep('''fn zeros(len: usize) -> Vec<u32> {''', '''fn zeros(len: usize, threads: usize) -> Vec<u32> {''')
        rep('''        unsafe { madvise(a as *mut u8, b - a, 14) }; // MADV_HUGEPAGE
                                                     // One first writer per huge page: racing faults each charge a 2 MiB page.
        (a..b)
            .step_by(1 << 21)
            .for_each(|p| unsafe { (p as *mut u8).write_volatile(0) });''',
            '''        unsafe { madvise(a as *mut u8, b - a, 14) }; // MADV_HUGEPAGE
                                                     // One first writer per huge page: racing faults each charge a 2 MiB page.
        parallel(threads, &|i| {
            let pages = (a + (i << 21)..b).step_by(threads << 21);
            pages.for_each(|p| unsafe { (p as *mut u8).write_volatile(0) })
        });''')
        rep('(zeros(n + 1), zeros(m))', '(zeros(n + 1, threads), zeros(m, threads))')
        rep('(vec![0; n], zeros(n + 1), zeros(m))', '(vec![0; n], zeros(n + 1, threads), zeros(m, threads))')
    elif v.startswith('p'):
        dist = int(v[1:])
        rep('''        for e in &a[i * m / threads..(i + 1) * m / threads] {
            let old = e.load(Relaxed);''', f'''        for k in i * m / threads..(i + 1) * m / threads {{
            if let Some(x) = a.get(k + {dist}) {{
                prefetch(&rank, (x.load(Relaxed) & mask) as usize); // the head's new id
            }}
            let (e, old) = (&a[k], a[k].load(Relaxed));''')
    elif v == 'd':
        rep('''    let block_len = n.div_ceil(threads);''', '''    let block_len = n.div_ceil(threads);
    let inv = (1u128 << 64) / block_len as u128 + 1; // u * inv >> 64 is u / block_len for u < 2^32''')
        rep('''lists[u as usize / block_len]''', '''lists[(u as u128 * inv >> 64) as usize]''')
    elif v == 'b':
        rep("""    fn put(d: u64) -> Option<Self>;""", """    /// The stored form of `d`, and whether `d` fits.
    fn put(d: u64) -> (Self, bool);""")
        rep("""    fn put(d: u64) -> Option<u32> {
        (d < u32::MAX as u64).then(|| !(d as u32))
    }""", """    fn put(d: u64) -> (u32, bool) {
        (!(d as u32), d < u32::MAX as u64)
    }""")
        rep("""    fn put(d: u64) -> Option<u64> {
        Some(!d)
    }""", """    fn put(d: u64) -> (u64, bool) {
        (!d, true)
    }""")
        rep("""        if d >= self.pool[i].get() {
            return false;
        }
        let Some(x) = D::put(d) else {
            self.cut = true;
            return false;
        };
        (self.pool[i], self.size) = (x, self.size + 1);
        self.heap.push(d >> SHIFT, v);
        true
    }""", """        // Whether `d` improves is data-dependent, so nothing branches on it.
        let ((x, fits), better) = (D::put(d), d < self.pool[i].get());
        let ok = better & fits;
        self.cut |= better & !fits;
        self.pool[i] = std::hint::select_unpredictable(ok, x, self.pool[i]);
        self.size += ok as usize;
        self.heap.push_if(ok, d >> SHIFT, v);
        ok
    }""")
        rep("""            // Only an improvement can make a shorter meeting; an unreached
            // other side reads as u64::MAX, which saturates.
            if me.reach(v, d + w as u64) {
                best = best.min((d + w as u64).saturating_add(other.get(v)));
            }""", """            // Any s-v-t path bounds the answer, improvement or not; an unreached
            // other side reads as u64::MAX, which saturates.
            me.reach(v, d + w as u64);
            best = best.min((d + w as u64).saturating_add(other.get(v)));""")
        rep("""    fn push(&mut self, k: u64, v: u32) {
        self.buckets[64 - (k ^ self.last).leading_zeros() as usize].push((k as u32, v));
    }""", """    fn push(&mut self, k: u64, v: u32) {
        self.buckets[64 - (k ^ self.last).leading_zeros() as usize].push((k as u32, v));
    }

    /// `push` if `ok`, without branching on it: the entry is always written
    /// past the end, and counted only if `ok`.
    fn push_if(&mut self, ok: bool, k: u64, v: u32) {
        let b = &mut self.buckets[64 - (k ^ self.last).leading_zeros() as usize];
        b.reserve(1);
        unsafe { b.as_mut_ptr().add(b.len()).write((k as u32, v)) };
        unsafe { b.set_len(b.len() + ok as usize) };
    }""")
    elif v == 'r':
        rep("""    let (n, m, mask) = (rank.len(), fwd.adj.len(), (1 << bits) - 1);
    let span = |i: usize| i * n / threads..(i + 1) * n / threads;
    let Csr { mut first, mut adj } = spare;
    first.fill(0);
    let (f, a) = (atomic(&mut first), atomic(&mut fwd.adj));
    parallel(threads, &|i| {
        for e in &a[i * m / threads..(i + 1) * m / threads] {
            let old = e.load(Relaxed);
            let head = !rank[(old & mask) as usize];
            e.store(head | old & !mask, Relaxed);
            f[head as usize].fetch_add(1, Relaxed);
        }
    });
    drop(rank);
    ends(f, threads);
    let mine = |i: usize| span(i).flat_map(|u| edges(&fwd, u).iter().map(move |&e| (u as u32, e)));
    let a = atomic(&mut adj);
    parallel(threads, &|i| {
        for (u, e) in mine(i) {
            let p = f[(e & mask) as usize].fetch_sub(1, Relaxed) - 1;
            a[p as usize].store(u | e & !mask, Relaxed);
        }
    });
    [fwd, Csr { first, adj }]""", """    let (n, mask) = (rank.len(), (1 << bits) - 1);
    let span = |i: usize| i * n / threads..(i + 1) * n / threads;
    let Csr { mut first, mut adj } = spare;
    first[n] = 0;
    let (f, a, wait) = (atomic(&mut first), atomic(&mut fwd.adj), &Barrier::new(threads));
    // Thread i owns the counts of the nodes in span(i) and updates them with
    // plain loads and stores. Edges into its span from other spans wait until
    // every owner is done and then use atomics, so few locked instructions
    // (full barriers on x86) stall the loops.
    let own = |i: usize, h: u32| span(i).contains(&(h as usize));
    parallel(threads, &|i| {
        f[span(i)].iter().for_each(|c| c.store(0, Relaxed));
        let mut later = vec![];
        for e in &a[fwd.first[span(i).start] as usize..fwd.first[span(i).end] as usize] {
            let old = e.load(Relaxed);
            let head = !rank[(old & mask) as usize];
            e.store(head | old & !mask, Relaxed);
            match own(i, head) {
                true => f[head as usize].store(f[head as usize].load(Relaxed) + 1, Relaxed),
                false => later.push(head),
            }
        }
        wait.wait();
        later.iter().for_each(|&h| _ = f[h as usize].fetch_add(1, Relaxed));
    });
    drop(rank);
    ends(f, threads);
    let a = atomic(&mut adj);
    parallel(threads, &|i| {
        let mut later = vec![];
        for u in span(i) {
            for &e in edges(&fwd, u) {
                let h = (e & mask) as usize;
                if !own(i, h as u32) {
                    later.push((u as u32, e));
                    continue;
                }
                let p = f[h].load(Relaxed) - 1;
                f[h].store(p, Relaxed);
                a[p as usize].store(u as u32 | e & !mask, Relaxed);
            }
        }
        wait.wait();
        for (u, e) in later {
            let p = f[(e & mask) as usize].fetch_sub(1, Relaxed) - 1;
            a[p as usize].store(u | e & !mask, Relaxed);
        }
    });
    [fwd, Csr { first, adj }]""")
        rep("""use std::sync::atomic::{AtomicI64, AtomicU32, AtomicU64, AtomicUsize, Ordering::Relaxed};""",
            """use std::sync::atomic::{AtomicI64, AtomicU32, AtomicU64, AtomicUsize, Ordering::Relaxed};
use std::sync::Barrier;""")
    else:
        raise SystemExit('unknown variant ' + v)
open(dst, 'w').write(s)
print('ok', vs)
