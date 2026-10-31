#[cfg(test)]
mod low32_review {
    use super::*;
    use std::collections::HashMap as TestMap;
    fn name_for(mut n: usize) -> [u8; 10] {
        let mut out = *b"NameAAAAAA";
        for i in (4..10).rev() { out[i] = b'A' + (n % 26) as u8; n /= 26; }
        assert_eq!(n, 0); out
    }
    fn leak(v: &[u8]) -> &'static [u8] { Box::leak(v.to_vec().into_boxed_slice()) }
    #[test]
    fn fingerprint_layout_and_promotion() {
        assert_eq!(std::mem::size_of::<Event>(), 12);
        let low = 0xdead_beefu64;
        let mut d = OwnerDict::default(); let mut vals = Vec::new();
        for i in 0..50_000usize {
            let full = ((i as u64) << 32) | low;
            assert_eq!((full as u32) as u64, low);
            assert_eq!(((full as u128 * 12) >> 64) as usize, 0);
            let name = name_for(i); let group = [0, 63, 64, 255, 256, 575][i % 6];
            assert_eq!(d.see(leak(&name), (full as u32) as u64, group, 9), 1);
            vals.push((name, group));
        }
        assert_eq!(d.heads[&low], PROMOTED); assert_eq!(d.promoted[&low].len(), 50_000);
        for (name, group) in vals.iter().rev() {
            assert_eq!(d.see(leak(name), low, *group, 9), 0);
            let other = (*group + 1) % 576;
            assert_eq!(d.see(leak(name), low, other, 9), 1);
            assert_eq!(d.see(leak(name), low, other, 9), 0);
        }
        assert_eq!(d.entries.len(), 50_000); assert_eq!(d.bits.len(), 50_000 * 9);
    }
    #[test]
    fn real_collisions_route_and_compare_exact_names() {
        let mut seen: TestMap<u32, Vec<(u64, [u8; 10], usize)>> = TestMap::new();
        let mut same = None; let mut different = None;
        let mut seed=0x8f3c21ad9d71e635u64;
        for _ in 0..1_000_000usize {
            let mut n=[b'A';10];
            for c in &mut n { seed ^= seed << 13; seed ^= seed >> 7; seed ^= seed << 17; *c=b'A'+(seed%26) as u8; }
            let h=name_hash(&n); let owner=((h as u128 * 12) >> 64) as usize;
            let old=seen.entry(h as u32).or_default();
            for &(h0,n0,o0) in old.iter() {
                if h0!=h && n0!=n {
                    if o0==owner && same.is_none() { same=Some((h0,n0,o0,h,n,owner)); }
                    if o0!=owner && different.is_none() { different=Some((h0,n0,o0,h,n,owner)); }
                }
            }
            old.push((h,n,owner)); if same.is_some() && different.is_some() {break;}
        }
        for (h0,n0,o0,h1,n1,o1) in [same.expect("same owner collision"),different.expect("different owner collision")] {
            assert_ne!(h0,h1); assert_eq!(h0 as u32,h1 as u32);
            let mut dicts:Vec<OwnerDict>=(0..12).map(|_| OwnerDict::default()).collect();
            for g in [0usize,63,64,255] {
                assert_eq!(dicts[o0].see(leak(&n0),h0 as u32 as u64,g,4),1);
                assert_eq!(dicts[o1].see(leak(&n1),h1 as u32 as u64,g,4),1);
                assert_eq!(dicts[o0].see(leak(&n0),h0 as u32 as u64,g,4),0);
                assert_eq!(dicts[o1].see(leak(&n1),h1 as u32 as u64,g,4),0);
            }
            assert_eq!(dicts.iter().map(|d|d.entries.len()).sum::<usize>(),2);
        }
    }
}
