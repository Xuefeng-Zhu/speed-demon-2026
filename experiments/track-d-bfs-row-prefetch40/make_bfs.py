import sys
s=open(sys.argv[1]).read(); v=sys.argv[3]
def rep(a,b):
    global s
    assert s.count(a)==1,a[:60]; s=s.replace(a,b)
rep('''    let next = AtomicU64::new(0);
    parallel(threads, &|i| {
        let mut roots''','''    let head = |e: u32| (e & ((1 << bits) - 1)) as usize;
    let next = AtomicU64::new(0);
    parallel(threads, &|i| {
        let mut roots''')
stages={
 'full':'''                // Nodes queued ahead: their row bounds, rows and heads' claims.
                if let Some(&v) = mine.get(k + 16) {
                    prefetch(&g.first, v as usize);
                }
                if let Some(&v) = mine.get(k + 8) {
                    prefetch(&g.adj, g.first[v as usize] as usize);
                }
                if let Some(&v) = mine.get(k + 4) {
                    edges(g, v as usize).iter().for_each(|&e| prefetch(r, head(e)));
                }
''',
 'two':'''                // Nodes queued ahead: their rows, then their heads' claims.
                if let Some(&v) = mine.get(k + 8) {
                    prefetch(&g.adj, g.first[v as usize] as usize);
                }
                if let Some(&v) = mine.get(k + 4) {
                    edges(g, v as usize).iter().for_each(|&e| prefetch(r, head(e)));
                }
''',
 'rows':'''                // Nodes queued ahead: their row bounds, then their rows.
                if let Some(&v) = mine.get(k + 16) {
                    prefetch(&g.first, v as usize);
                }
                if let Some(&v) = mine.get(k + 8) {
                    prefetch(&g.adj, g.first[v as usize] as usize);
                }
''',
 'row':'''                // A node queued ahead: start loading its row.
                if let Some(&v) = mine.get(k + 8) {
                    prefetch(&g.adj, g.first[v as usize] as usize);
                }
''',
 'claims':'''                // A node queued ahead: start loading its heads' claims.
                if let Some(&v) = mine.get(k + 4) {
                    edges(g, v as usize).iter().for_each(|&e| prefetch(r, head(e)));
                }
''',
}
rep('''            'grow: while k < mine.len() {
''','''            'grow: while k < mine.len() {
'''+stages[v])
rep('''                    let v = (e & ((1 << bits) - 1)) as usize;
                    if mine.len() == CLUSTER {''','''                    let v = head(e);
                    if mine.len() == CLUSTER {''')
open(sys.argv[2],'w').write(s)
