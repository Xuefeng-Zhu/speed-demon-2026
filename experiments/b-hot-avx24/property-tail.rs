
#[cfg(test)]
mod hot_property {
    use super::*;
    fn lcg(x: &mut u64) -> u64 { *x = x.wrapping_mul(6364136223846793005).wrapping_add(1442695040888963407); *x }
    #[test]
    fn selection_exact_and_empty_padding() {
        let mut p = Plan { slots: vec![MISS; 8192], ..Default::default() };
        let mut corpus = Vec::new();
        let mut x = 0x3437_0123_9876_aaaa;
        for _ in 0..1800 {
            let n = (lcg(&mut x) % 8 + 1) as usize;
            let mut b = Vec::new();
            for _ in 0..n { b.push(b"abcdefghijklmnopqrstuvwxyz0123456789"[(lcg(&mut x) % 36) as usize]); }
            p.intern(&b, 0); corpus.push(b);
        }
        p.build_short();
        assert_eq!(p.lookup_token(&[], 0, 0), MISS);
        let mut freq = vec![0; p.keys.len()];
        for f in &mut freq { *f = (lcg(&mut x) >> 32) as u32; }
        p.build_hot(&freq);
        assert_eq!(p.lookup_token(&[], 0, 0), MISS);
        let hot_keys = p.hot_keys;
        let hot_ids = p.hot_ids;
        for i in 0..8 {
            assert_ne!(hot_ids[i], MISS);
            assert_eq!(p.keys[hot_ids[i] as usize].0[0], hot_keys[i]);
        }
        for b in &corpus {
            let mut upper=b.clone(); upper.make_ascii_uppercase();
            let got = p.lookup_token(&upper, 0, upper.len());
            p.hot_keys=[0;8];
            let expected = p.lookup_token(&upper, 0, upper.len());
            assert_eq!(got, expected);
            p.hot_keys=hot_keys;
        }
        for _ in 0..20000 {
            let n = (lcg(&mut x) % 8 + 1) as usize;
            let mut b = Vec::new();
            for _ in 0..n { b.push(b"abcdefghijklmnopqrstuvwxyz0123456789"[(lcg(&mut x) % 36) as usize]); }
            let got=p.lookup_token(&b, 0, n);
            p.hot_keys=[0;8];
            let expected=p.lookup_token(&b,0,n);
            assert_eq!(got,expected);
            p.hot_keys=hot_keys;
        }
        let mut one = vec![0; p.keys.len()]; one[0] = 1;
        p.build_hot(&one);
        assert_eq!(p.hot_ids.iter().filter(|&&id| id != MISS).count(), 1);
        assert_eq!(p.lookup_token(&[], 0, 0), MISS);
        p.build_hot(&vec![0;p.keys.len()]);
        assert_eq!(p.hot_keys,[0;8]);
        for b in &corpus { assert_ne!(p.lookup_token(b,0,b.len()),MISS); }
    }
}
