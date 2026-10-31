import sys
s=open(sys.argv[1]).read()
def rep(a,b):
    global s
    assert s.count(a)==1,a[:70]; s=s.replace(a,b)
rep('    heap: RadixHeap,','    heap: RadixHeap<D>,')
rep('''        (self.pool[i], self.size) = (x, self.size + 1);
        self.heap.push(d >> SHIFT, v);''','''        (self.pool[i], self.size) = (x, self.size + 1);
        self.heap.push(x, v);''')
rep('''        let (key, u) = ([a, b][side], me.heap.buckets[0].pop().unwrap().1);''','''        let (x, u) = me.heap.buckets[0].pop().unwrap();''')
rep('''        let d = me.get(u);
        if d >> SHIFT < key {
            continue; // stale: already expanded from an earlier bucket
        }''','''        // The entry's own distance: if `u` has since improved, this repeats
        // work that cannot beat the newer entry, but stays a real path length.
        let d = x.get();''')
i=s.index('/// Monotone priority queue:'); j=s.index('\nfn main()')
s=s[:i]+'''/// Monotone priority queue over `distance >> SHIFT`: keys pushed are never
/// below the last key popped. Bucket i holds entries whose key's highest bit
/// differing from `last` is bit i - 1. An entry is a stored distance and its
/// node, so a pop needs no lookup to know the distance it was queued with.
struct RadixHeap<D> {
    last: u64,
    buckets: [Vec<(D, u32)>; 65],
}

impl<D: Dist> RadixHeap<D> {
    fn push(&mut self, x: D, v: u32) {
        let k = x.get() >> SHIFT;
        self.buckets[64 - (k ^ self.last).leading_zeros() as usize].push((x, v));
    }

    /// The smallest key, after moving every entry with that key into bucket 0.
    fn top(&mut self) -> Option<u64> {
        if self.buckets[0].is_empty() {
            let i = self.buckets.iter().position(|b| !b.is_empty())?;
            let mut b = std::mem::take(&mut self.buckets[i]);
            self.last = b.iter().map(|e| e.0.get() >> SHIFT).min().unwrap();
            b.drain(..).for_each(|(x, v)| self.push(x, v));
            self.buckets[i] = b; // keeps its allocation
        }
        Some(self.last)
    }
}
'''+s[j:]
open(sys.argv[2],'w').write(s)
