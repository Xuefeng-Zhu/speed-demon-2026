#[cfg(test)]
mod pool_boundary_independent {
    use super::*;
    use std::collections::BTreeSet;

    fn audit(h: &FastHeap) {
        let mut seen = vec![false; h.nodes.len()];
        let mut queued = 0usize;
        for (bucket, &head) in h.head.iter().enumerate() {
            let mut p = head;
            let mut low = u64::MAX;
            while p != END {
                let i = p as usize;
                assert!(i < seen.len() && !seen[i], "duplicate or invalid queued node");
                seen[i] = true;
                queued += 1;
                let node = h.nodes[i];
                low = low.min(node.key);
                assert_eq!(h.slot(node.key), bucket, "node in wrong radix bucket");
                p = node.next;
            }
            assert_eq!(h.min[bucket], low, "stale cached minimum");
        }
        let mut p = h.free;
        while p != END {
            let i = p as usize;
            assert!(i < seen.len() && !seen[i], "free-list cycle or shared node");
            seen[i] = true;
            p = h.nodes[i].next;
        }
        assert!(seen.iter().all(|&x| x), "orphan node");
        assert_eq!(queued, h.count);
    }

    #[test]
    fn actual_pool_limit_refill_and_redistribution() {
        assert_eq!(POOL_CAP, 65_536);
        let mut h = FastHeap::new();
        let mut expected = BTreeSet::<(u64, u32)>::new();
        for epoch in 0..5u32 {
            h.clear(); expected.clear();
            for i in 0..POOL_CAP as u32 {
                let key = u64::from(i.wrapping_mul(2_654_435_761));
                assert!(h.push(key, i));
                assert!(expected.insert((key, i)));
            }
            assert_eq!(h.nodes.len(), POOL_CAP);
            let before = (h.count, h.nodes.len(), h.free, h.last, h.head, h.min);
            assert!(!h.push(u64::from(u32::MAX), u32::MAX));
            assert_eq!((h.count, h.nodes.len(), h.free, h.last, h.head, h.min), before);
            audit(&h);

            for _ in 0..POOL_CAP / 2 {
                let min = expected.first().unwrap().0;
                assert_eq!(h.top(), Some(min));
                let item = h.pop();
                assert!(expected.remove(&item));
            }
            audit(&h);
            let last = h.last;
            for i in 0..POOL_CAP as u32 / 2 {
                let key = last + u64::from(i.wrapping_mul(2_246_822_519));
                let vertex = POOL_CAP as u32 + i + epoch * 100_000;
                assert!(h.push(key, vertex));
                assert!(expected.insert((key, vertex)));
            }
            assert_eq!(h.nodes.len(), POOL_CAP, "freed slots were not reused");
            assert!(!h.push(h.last + u64::from(u32::MAX), u32::MAX));
            audit(&h);
            while !expected.is_empty() {
                assert_eq!(h.top(), Some(expected.first().unwrap().0));
                assert!(expected.remove(&h.pop()));
            }
            assert_eq!(h.top(), None);
            assert_eq!(h.count, 0);
            audit(&h);
        }
        h.clear();
        assert_eq!(h.count, 0);
        assert!(h.nodes.is_empty());
        assert!(h.head.iter().all(|&p| p == END));
        assert_eq!(h.free, END);
        assert_eq!(h.last, 0);
    }
}
