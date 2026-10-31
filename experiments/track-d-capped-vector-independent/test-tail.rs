#[cfg(test)]
mod independent_vector_heap_tests {
    use super::*;
    use std::collections::BTreeMap;

    fn put(model: &mut BTreeMap<u64, Vec<u32>>, k: u64, v: u32) {
        model.entry(k).or_default().push(v);
    }
    fn check_pop(heap: &mut FastHeap, model: &mut BTreeMap<u64, Vec<u32>>) -> u64 {
        let (&expected, _) = model.first_key_value().expect("model not empty");
        assert_eq!(heap.top(), Some(expected));
        let (key, vertex) = heap.pop();
        assert_eq!(key, expected);
        let values = model.get_mut(&key).unwrap();
        let i = values.iter().position(|&v| v == vertex).expect("vertex exists");
        values.swap_remove(i);
        if values.is_empty() { model.remove(&key); }
        key
    }

    #[test]
    fn empty_full_reject_clear_reuse() {
        let mut heap = FastHeap::new();
        assert_eq!(heap.top(), None);
        assert_eq!(heap.buckets.len(), 33);
        assert!(heap.buckets.iter().all(|b| b.capacity() >= POOL_CAP));
        for i in 0..POOL_CAP {
            let k = (i as u64).wrapping_mul(2_654_435_761) % (u32::MAX as u64);
            assert!(heap.push(k, i as u32));
        }
        assert_eq!(heap.count, POOL_CAP);
        assert!(!heap.push(0, 0));
        assert_eq!(heap.count, POOL_CAP);
        heap.clear();
        assert_eq!(heap.top(), None);
        assert_eq!(heap.count, 0);
        assert_eq!(heap.last, 0);
        assert!(heap.buckets.iter().all(Vec::is_empty));
        if POOL_CAP > 0 {
            assert!(heap.push(0, 7));
            assert_eq!(heap.top(), Some(0));
            assert_eq!(heap.pop(), (0, 7));
            assert_eq!(heap.top(), None);
        }
    }

    #[test]
    fn all_33_buckets_equal_keys_and_maximum() {
        if POOL_CAP < 100 { return; }
        let mut heap = FastHeap::new();
        let mut model = BTreeMap::new();
        for b in 0..33 {
            let k = if b == 0 { 0 } else { 1_u64 << (b - 1) };
            for offset in 0..3 {
                let v = b as u32 * 3 + offset;
                assert!(heap.push(k, v)); put(&mut model, k, v);
            }
            assert!(!heap.buckets[b].is_empty());
        }
        let k = u32::MAX as u64 - 1;
        assert!(heap.push(k, u32::MAX)); put(&mut model, k, u32::MAX);
        while !model.is_empty() { check_pop(&mut heap, &mut model); }
        assert_eq!(heap.top(), None);
        assert_eq!(heap.count, 0);
    }

    #[test]
    fn full_then_interleave_redistribute_and_refill() {
        if POOL_CAP == 0 { return; }
        let mut heap = FastHeap::new();
        let mut model = BTreeMap::new();
        let mut seed = 0x125b_91e7_64d3_aa17_u64;
        for i in 0..POOL_CAP {
            seed = seed.wrapping_mul(6_364_136_223_846_793_005).wrapping_add(1);
            let k = (seed >> 16) % (u32::MAX as u64);
            assert!(heap.push(k, i as u32)); put(&mut model, k, i as u32);
        }
        let mut last = 0;
        let steps = POOL_CAP.min(20_000);
        for i in 0..steps {
            last = check_pop(&mut heap, &mut model);
            seed = seed.wrapping_mul(6_364_136_223_846_793_005).wrapping_add(1);
            let width = u32::MAX as u64 - last;
            let k = last + (seed % width);
            let v = (POOL_CAP + i) as u32;
            assert!(heap.push(k, v)); put(&mut model, k, v);
            assert_eq!(heap.count, POOL_CAP);
            assert!(!heap.push(k, v));
        }
        while !model.is_empty() {
            let k = check_pop(&mut heap, &mut model);
            assert!(k >= last); last = k;
        }
        assert_eq!(heap.top(), None);
        heap.clear();
        assert_eq!(heap.count, 0);
    }
}
