#[cfg(test)]
mod independent_rowcache_tests {
    use super::*;
    use std::collections::{HashMap, HashSet};

    fn names() -> Vec<&'static [u8]> {
        let mut result = vec![b"".as_slice(), b"A".as_slice(), b"A ".as_slice(), b"Ann \"\"X\"\"".as_slice()];
        for i in 0..516 {
            result.push(Box::leak(format!("Name{i:04}{}", " ".repeat(i % 7)).into_bytes().into_boxed_slice()));
        }
        result
    }

    fn hash_for(index: usize, mode: u32) -> u64 {
        match mode {
            // All names use the same full prehash; the ninth promotes the chain.
            0 => 0,
            1 => u64::MAX,
            // All names alias the same direct-map slot, with distinct hashes.
            2 => (index as u64).wrapping_mul(CACHE_SLOTS as u64),
            // A mix of promoted full-hash collisions and cache-index collisions.
            3 => ((index / 12) as u64).wrapping_mul(CACHE_SLOTS as u64) + 17,
            _ => (index as u64).wrapping_mul(0x9e3779b97f4a7c15),
        }
    }

    #[test]
    fn independent_replacement_and_promotion_oracle() {
        let input = names();
        for mode in 0..5 {
            for &groups in &[1usize, 63, 64, 65, 240, 241, 256, 257] {
                let words = groups.div_ceil(64);
                let mut dict = OwnerDict::default();
                let mut seen = HashSet::new();
                let mut expected_name_hash = HashMap::new();
                // Force promotion, then hit entries from before promotion repeatedly.
                for step in 0..200_000usize {
                    let index = if step < input.len() { step } else {
                        let x = (step as u64).wrapping_mul(0xd1342543de82ef95).rotate_left(19);
                        (x as usize) % input.len()
                    };
                    let group = (step.wrapping_mul(73) ^ (step >> 3)) % groups;
                    let hash = hash_for(index, mode);
                    let name = input[index];
                    let duplicate_allocation: &'static [u8] = if step < 100 && step % 3 == 0 {
                        Box::leak(name.to_vec().into_boxed_slice())
                    } else { name };
                    let expected = seen.insert((name, group));
                    let actual = dict.see(duplicate_allocation, hash, group, words);
                    assert_eq!(actual, i64::from(expected), "mode={mode}, groups={groups}, step={step}, index={index}, group={group}");
                    expected_name_hash.insert(name, hash);
                }
                assert_eq!(dict.entries.len(), input.len());
                assert_eq!(dict.bits.len(), dict.entries.len() * words);
                assert_eq!(dict.cache.len(), CACHE_SLOTS);
                for &(h, row) in &dict.cache {
                    if row != NONE {
                        assert!(row < dict.entries.len());
                        assert_eq!(expected_name_hash[dict.entries[row].0], h);
                    }
                }
                if mode <= 1 { assert_eq!(dict.heads[&hash_for(0, mode)], PROMOTED); }
            }
        }
    }
}
