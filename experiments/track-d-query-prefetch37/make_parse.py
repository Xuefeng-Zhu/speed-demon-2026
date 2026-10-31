import sys
s=open(sys.argv[1]).read(); opts=sys.argv[3].split(',')
def rep(a,b):
    global s
    assert s.count(a)==1,a[:60]; s=s.replace(a,b)
if 'chunks' in opts:
    k=sys.argv[4]
    rep('''    let cuts: Vec<usize> = (0..=threads).map(|i| line_end((i * len / threads).max(1) - 1)).collect();''',
        '''    // Many more pieces than threads, taken in turn, so no thread waits on a slow one.
    let pieces = threads * %s;
    let cuts: Vec<usize> = (0..=pieces).map(|i| line_end((i * len / pieces).max(1) - 1)).collect();
    let next = AtomicUsize::new(0);''' % k)
    rep('''        each_edge(text, cuts[i], cuts[i + 1], |u, v, w| {
            lists[u as usize / block_len].push((u as u64) << 32 | (v | w.min(wide) << bits) as u64);
            if w >= wide {
                big.push((u, v, w));
            }
        });''','''        let mut c = next.fetch_add(1, Relaxed);
        while c < pieces {
            each_edge(text, cuts[c], cuts[c + 1], |u, v, w| {
                lists[u as usize / block_len].push((u as u64) << 32 | (v | w.min(wide) << bits) as u64);
                if w >= wide {
                    big.push((u, v, w));
                }
            });
            c = next.fetch_add(1, Relaxed);
        }''')
    rep('let parts = parallel(threads, &|i| {','let parts = parallel(threads, &|_| {')
if 'populate' in opts:
    rep('mmap(std::ptr::null_mut(), len, 1, 2, file.as_raw_fd(), 0)','mmap(std::ptr::null_mut(), len, 1, 2 | 0x8000, file.as_raw_fd(), 0)')
open(sys.argv[2],'w').write(s)
