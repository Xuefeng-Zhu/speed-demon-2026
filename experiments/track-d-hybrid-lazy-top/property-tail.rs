#[cfg(test)]
mod lazy_top_test {
    use super::*;
    use std::collections::BTreeMap;
    #[test]
    fn monotone_lower_bounds_and_queue_contents() {
        let mut heaps = [FastHeap::new(), FastHeap::new()];
        let mut expected = [BTreeMap::<u64, Vec<u32>>::new(), BTreeMap::<u64, Vec<u32>>::new()];
        let mut z = 0x91a2_b3c4_d5e6_f701u64;
        for step in 0..250_000u32 {
            z ^= z << 13; z ^= z >> 7; z ^= z << 17;
            if step % 977 == 0 {
                for i in 0..2 { heaps[i].clear(); expected[i].clear(); }
            }
            let side = (z & 1) as usize;
            if expected[side].is_empty() || z % 5 < 3 {
                let delta = match z % 13 { 0 => 0, 1 => 1, 2 => 1 << 20, _ => (z >> 8) % 2048 };
                let key = heaps[side].last + delta;
                assert!(key < u32::MAX as u64);
                assert!(heaps[side].push(key, step));
                expected[side].entry(key).or_default().push(step);
            } else if z % 5 == 3 {
                let top = heaps[side].top().unwrap();
                let (key, value) = heaps[side].pop();
                assert_eq!(top, key);
                assert_eq!(expected[side].first_key_value().unwrap().0, &key);
                let vals = expected[side].get_mut(&key).unwrap();
                let i = vals.iter().position(|&v| v == value).unwrap();
                vals.swap_remove(i);
                if vals.is_empty() { expected[side].remove(&key); }
            }
            for i in 0..2 {
                let count: usize = expected[i].values().map(Vec::len).sum();
                assert_eq!(heaps[i].count, count);
                if let Some((&min, _)) = expected[i].first_key_value() {
                    assert!(heaps[i].last <= min);
                }
            }
        }
    }
}
