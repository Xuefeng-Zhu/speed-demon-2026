#[cfg(test)]
mod cache_review {
    use super::*;
    use std::collections::HashSet;
    #[test]
    fn cache_clashes_growth_and_promoted_names() {
        let mut d=OwnerDict::default();
        let names: Vec<&'static [u8]> = (0..1200).map(|i| Box::leak(format!("test-name-{i}").into_bytes().into_boxed_slice()) as &'static [u8]).collect();
        let mut seen=HashSet::new();
        let mut r=12345u64;
        for iteration in 0..180_000 {
            r^=r<<13;r^=r>>7;r^=r<<17;
            let id=(r as usize)%names.len();
            let g=((r >> 20) as usize)%513;
            // 600 distinct names share one hash, forcing the inner collision
            // chain to promote; other hashes collide in a one-slot cache.
            let h=if id<600 {0} else { (id as u64) << 15 };
            assert_eq!(d.see(names[id],h,g,9), seen.insert((id,g)) as i64, "iteration {iteration}");
        }
        assert!(d.promoted.contains_key(&0));
        for i in 0..names.len() { let h=if i<600 {0}else{(i as u64)<<15}; for g in [0,63,64,512] {
            assert_eq!(d.see(names[i],h,g,9),seen.insert((i,g)) as i64);
            assert_eq!(d.see(names[i],h,g,9),0);
        }}
    }
}
