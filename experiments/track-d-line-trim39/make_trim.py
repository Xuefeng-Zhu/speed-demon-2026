import sys
s=open(sys.argv[1]).read()
def rep(a,b):
    global s
    assert s.count(a)==1,(s.count(a),a[:70]); s=s.replace(a,b)
# use std::mem::take
rep('use std::{fs, fs::File, os::fd::AsRawFd, thread};','use std::{fs, fs::File, mem::take, os::fd::AsRawFd, thread};')
# ends: name the per-chunk sum so the parallel call fits one line
rep('''    let sums = parallel(parts.len(), &|i| parts[i].iter().map(|c| c.load(Relaxed)).sum::<u32>());''',
'''    let sum = |c: &[AtomicU32]| c.iter().map(|c| c.load(Relaxed)).sum::<u32>();
    let sums = parallel(parts.len(), &|i| sum(parts[i]));''')
# each_edge inlined into the parse loop
rep('''/// Calls `f(u, v, w)` for every `u v w` line in `text[p..end]`.
fn each_edge(text: &[u8], mut p: usize, end: usize, mut f: impl FnMut(u32, u32, u32)) {
    while p < end {
        let (u, v) = (num(text, &mut p), num(text, &mut p));
        f(u, v, num(text, &mut p));
    }
}

''','')
rep('''    let line_end = |p: usize| p + text[p..].iter().position(|&b| b == b'\\n').map_or(len - p, |i| i + 1);''',
'''    let line_end = |p: usize| (p..len).find(|&i| text[i] == b'\\n').map_or(len, |i| i + 1);''')
rep('''    let cuts: Vec<usize> = (0..=threads).map(|i| line_end((i * len / threads).max(1) - 1)).collect();
''','''    let cut = |i: usize| line_end((i * len / threads).max(1) - 1);
''')
rep('''        each_edge(text, cuts[i], cuts[i + 1], |u, v, w| {
            lists[u as usize / block_len].push((u as u64) << 32 | (v | w.min(wide) << bits) as u64);
            if w >= wide {
                big.push((u, v, w));
            }
        });''','''        let (mut p, end) = (cut(i), cut(i + 1));
        while p < end {
            let (u, v, w) = (num(text, &mut p), num(text, &mut p), num(text, &mut p));
            lists[u as usize / block_len].push((u as u64) << 32 | (v | w.min(wide) << bits) as u64);
            if w >= wide {
                big.push((u, v, w));
            }
        }''')
rep('''            let col: Vec<_> = buckets.iter_mut().map(|b| std::mem::take(&mut b[j])).collect();''',
'''            let col: Vec<_> = buckets.iter_mut().map(|b| take(&mut b[j])).collect();''')
rep('''            let (adj, rest) = std::mem::take(&mut adj_rest).split_at_mut(size);
            let lo = j * block_len;''','''            let (adj, rest) = take(&mut adj_rest).split_at_mut(size);
            let at = move |e: u64| (e >> 32) as usize - j * block_len;''')
rep('''                col.iter().flatten().for_each(|&e| first[(e >> 32) as usize - lo] += 1);''',
'''                col.iter().flatten().for_each(|&e| first[at(e)] += 1);''')
rep('''                        let c = &mut first[(e >> 32) as usize - lo];''','''                        let c = &mut first[at(e)];''')
# claim takes &usize so filter/find can use it directly
rep('''    let claim = |v: usize| r[v].load(Relaxed) == 0 && r[v].compare_exchange(0, 1, Relaxed, Relaxed).is_ok();''',
'''    let claim = |&v: &usize| r[v].load(Relaxed) == 0 && r[v].compare_exchange(0, 1, Relaxed, Relaxed).is_ok();''')
rep('''        while let Some(root) = seed.take().filter(|&v| claim(v)).or_else(|| roots.find(|&v| claim(v))) {''',
'''        while let Some(root) = seed.take().filter(claim).or_else(|| roots.find(claim)) {''')
rep('''                    if claim(v) {''','''                    if claim(&v) {''')
# Side::new: shorthand fields keep the heap literal on one line
rep('''    fn new(n: usize) -> Self {
        Side {''','''    fn new(n: usize) -> Self {
        let (last, buckets) = (0, std::array::from_fn(|_| Vec::new()));
        Side {''')
rep('''            heap: RadixHeap { last: 0, buckets: std::array::from_fn(|_| Vec::new()) },''','''            heap: RadixHeap { last, buckets },''')
open(sys.argv[2],'w').write(s)
s=open(sys.argv[2]).read()
rep('''    let claim = |&v: &usize| r[v].load(Relaxed) == 0 && r[v].compare_exchange(0, 1, Relaxed, Relaxed).is_ok();''',
'''    // Unclaimed is 0; a claimed node holds 1 or its complemented id, never 0,
    // so raising a slot to at least 1 claims it only if it was free.
    let claim = |&v: &usize| r[v].load(Relaxed) == 0 && r[v].fetch_max(1, Relaxed) == 0;''')
open(sys.argv[2],'w').write(s)
