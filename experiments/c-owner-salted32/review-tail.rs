#[cfg(test)]
mod independent_low32 {
    use super::*;
    use std::collections::HashMap as TestMap;
    fn name_for(mut n: usize) -> [u8; 10] {
        let mut out = *b"NameAAAAAA";
        for i in (4..10).rev() { out[i] = b'A' + (n % 26) as u8; n /= 26; }
        assert_eq!(n, 0);
        out
    }
    fn leak(v: &[u8]) -> &'static [u8] { Box::leak(v.to_vec().into_boxed_slice()) }
    #[test]
    fn layout_and_distinct_64bit_hashes_with_equal_fingerprint() {
        assert_eq!(std::mem::size_of::<Event>(), 12);
        let low = 0xdead_beefu32;
        let mut d = OwnerDict::default();
        let mut vals = Vec::new();
        for i in 0..50_000usize {
            let full = ((i as u64) << 32) | low as u64;
            assert_eq!(full as u32, low);
            assert_eq!(((full as u128 * 12) >> 64) as usize, 0);
            let name = name_for(i);
            let group = [0, 63, 64, 255, 256, 575][i % 6];
            assert_eq!(d.see(leak(&name), full as u32, group, 9), 1);
            vals.push((name, group));
        }
        assert_eq!(d.heads[&low], PROMOTED);
        assert_eq!(d.promoted[&low].len(), 50_000);
        for (name, group) in vals.iter().rev() {
            assert_eq!(d.see(leak(name), low, *group, 9), 0);
            let other = (*group + 1) % 576;
            assert_eq!(d.see(leak(name), low, other, 9), 1);
            assert_eq!(d.see(leak(name), low, other, 9), 0);
        }
        assert_eq!(d.entries.len(), 50_000);
        assert_eq!(d.bits.len(), 50_000 * 9);
        println!("PASS 50,000 synthetic distinct Fx64 values with identical low32 and owner; 100,000 exact names/groups");
    }
    #[test]
    fn real_fx64_collision_on_low32_with_same_owner() {
        let mut seen: TestMap<(u32, u8), (u64, [u8; 10])> = TestMap::new();
        let mut found = None;
        let mut seed=0x8f3c21ad9d71e635u64;
        for i in 0..1_000_000usize {
            let mut n=[b'A';10];
            for c in &mut n { seed ^= seed << 13; seed ^= seed >> 7; seed ^= seed << 17; *c=b'A'+(seed%26) as u8; }
            let h = BuildHasherDefault::<Fx>::default().hash_one(n.as_slice());
            let owner = ((h as u128 * 12) >> 64) as u8;
            let key = (h as u32, owner);
            if let Some((old, prev)) = seen.insert(key, (h, n)) {
                if old != h && prev != n { found = Some((old, prev, h, n, owner, i)); break; }
            }
        }
        let (h1, n1, h2, n2, owner, searched) = found.expect("no actual low32 collision found in 1M legal names");
        assert_ne!(h1,h2); assert_eq!(h1 as u32,h2 as u32);
        assert_eq!(((h1 as u128*12)>>64) as u8,owner);assert_eq!(((h2 as u128*12)>>64) as u8,owner);
        let mut d=OwnerDict::default();
        for g in [0usize, 63, 64, 255] {
            assert_eq!(d.see(leak(&n1), h1 as u32, g, 4), 1);
            assert_eq!(d.see(leak(&n2), h2 as u32, g, 4), 1);
            assert_eq!(d.see(leak(&n1), h1 as u32, g, 4), 0);
            assert_eq!(d.see(leak(&n2), h2 as u32, g, 4), 0);
        }
        assert_eq!(d.entries.len(),2);
        println!("COLLISION_NAMES {} {} {:016x} {:016x} {}",std::str::from_utf8(&n1).unwrap(),std::str::from_utf8(&n2).unwrap(),h1,h2,owner);
        println!("PASS actual Fx64 distinct-full/same-low32/same-owner pair after {} legal names, owner {}",searched+1,owner);
    }
}
