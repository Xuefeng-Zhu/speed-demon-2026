import sys
s=open(sys.argv[1]).read(); ring=sys.argv[3]
def rep(a,b):
    global s
    assert s.count(a)==1,a[:70]; s=s.replace(a,b)
i=s.index('/// Monotone priority queue: keys pushed are never below the last key popped.')
j=s.index('\nfn main()')
s=s[:i]+'''/// Ring slots in a search queue: keys within `RING` of the smallest one
/// share no slot, and farther keys wait in a heap.
const RING: usize = %s;

/// Monotone bucket queue: keys pushed are never below the current key
/// `last`. Keys in `[last, last + RING)` sit in ring slot `key %% RING`, a
/// stack of node ids; farther keys (past the occasional huge weight) wait in
/// a binary heap until the ring catches up with them.
struct Queue {
    last: u64,
    ring: Vec<Vec<u32>>,
    far: BinaryHeap<Reverse<(u64, u32)>>,
}

impl Queue {
    fn new() -> Self {
        Queue { last: 0, ring: (0..RING).map(|_| Vec::new()).collect(), far: BinaryHeap::new() }
    }

    fn push(&mut self, k: u64, v: u32) {
        if k < self.last + RING as u64 {
            self.ring[k as usize %% RING].push(v);
        } else {
            self.far.push(Reverse((k, v)));
        }
    }

    /// The entries with the current key.
    fn cur(&mut self) -> &mut Vec<u32> {
        &mut self.ring[self.last as usize %% RING]
    }

    /// The smallest key, after moving every entry with that key into `cur()`.
    fn top(&mut self) -> Option<u64> {
        let far = self.far.peek().map_or(u64::MAX, |r| r.0 .0);
        let end = far.min(self.last + RING as u64);
        while self.last < end && self.cur().is_empty() {
            self.last += 1;
        }
        if self.last < end {
            return Some(self.last);
        }
        if far == u64::MAX {
            return None; // the whole ring was empty
        }
        // Nothing in the ring comes before the heap's smallest key: jump
        // there and bring every heap entry that now fits into the ring.
        self.last = far;
        while let Some(&Reverse((k, v))) = self.far.peek().filter(|r| r.0 .0 < far + RING as u64) {
            self.far.pop();
            self.ring[k as usize %% RING].push(v);
        }
        Some(far)
    }

    fn clear(&mut self) {
        self.ring.iter_mut().for_each(Vec::clear);
        (self.last, self.far) = (0, BinaryHeap::new());
    }
}
''' % ring + s[j:]
rep('use std::sync::atomic::','use std::{cmp::Reverse, collections::BinaryHeap};\nuse std::sync::atomic::')
rep('    heap: RadixHeap,','    heap: Queue,')
rep('            heap: RadixHeap { last: 0, buckets: std::array::from_fn(|_| Vec::new()) },','            heap: Queue::new(),')
rep('''        self.heap.buckets.iter_mut().for_each(Vec::clear);
        (self.heap.last, self.size, self.cut) = (0, 0, false);''','''        self.heap.clear();
        (self.size, self.cut) = (0, false);''')
rep('''        let (key, u) = ([a, b][side], me.heap.buckets[0].pop().unwrap().1);''','''        let (key, u) = ([a, b][side], me.heap.cur().pop().unwrap());''')
rep('''        let q = &me.heap.buckets[0];
        if let Some(&(_, next)) = q.len().checked_sub(2).map(|i| &q[i]) {''','''        let q = me.heap.cur();
        if let Some(&next) = q.len().checked_sub(2).map(|i| &q[i]) {''')
rep('''        if let Some(&(_, next)) = q.last() {''','''        if let Some(&next) = q.last() {''')
open(sys.argv[2],'w').write(s)
