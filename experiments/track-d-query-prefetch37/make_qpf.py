import sys
s=open(sys.argv[1]).read(); mode=sys.argv[3]
def rep(a,b):
    global s
    assert s.count(a)==1,a[:60]; s=s.replace(a,b)
a='''        let (key, u) = ([a, b][side], me.heap.buckets[0].pop().unwrap().1);
        me.size -= 1;'''
if mode=='first':
    b=a+'''
        // The next node this side pops: start loading its row bounds.
        if let Some(&(_, next)) = me.heap.buckets[0].last() {
            prefetch(&net.graphs[side].first, next as usize);
        }'''
elif mode=='two':
    b=a+'''
        // The next two nodes this side pops: start loading their rows.
        let q = &me.heap.buckets[0];
        if let Some(&(_, next)) = q.len().checked_sub(2).map(|i| &q[i]) {
            prefetch(&net.graphs[side].first, next as usize);
        }
        if let Some(&(_, next)) = q.last() {
            let g = &net.graphs[side];
            prefetch(&g.adj, g.first[next as usize] as usize);
        }'''
elif mode=='dist':
    b=a+'''
        // The next node this side pops: start loading its row and distance.
        if let Some(&(_, next)) = me.heap.buckets[0].last() {
            let g = &net.graphs[side];
            prefetch(&g.adj, g.first[next as usize] as usize);
        }'''
rep(a,b)
open(sys.argv[2],'w').write(s)
