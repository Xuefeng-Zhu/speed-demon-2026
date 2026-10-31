#[cfg(test)]
mod tests {
    use super::*;
    use std::collections::HashSet;
    #[test]
    fn reset_clears_cache_collisions_promotions_and_bits() {
        let names: Vec<&'static [u8]> = (0..128)
            .map(|i| Box::leak(format!("name-{i:03} ").into_bytes().into_boxed_slice()) as &'static [u8])
            .collect();
        let mut d = OwnerDict::default();
        let mut checks = 0usize;
        for phase in 0..100 {
            d.reset();
            assert!(d.heads.is_empty() && d.entries.is_empty() && d.bits.is_empty() && d.promoted.is_empty());
            assert!(d.cache.iter().all(|&(_,r)| r==NONE));
            let groups = [1usize, 63, 64, 65, 241, 257][phase % 6];
            let words = groups.div_ceil(64);
            let mut seen = HashSet::new();
            for i in 0..4000 {
                let k = (i * 37 + i / 127 + phase) % names.len();
                let g = (i * 31 + i / 11 + phase) % groups;
                let hash = if phase % 2 == 0 { 0 } else { (k % 3) as u64 * 32768 };
                let expected = seen.insert((k, g)) as i64;
                assert_eq!(d.see(names[k], hash, g, words), expected, "phase={phase} k={k} g={g}");
                checks += 1;
            }
        }
        assert_eq!(checks, 400_000);
    }
}
