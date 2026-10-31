#[cfg(test)]
mod fingerprint_tests {
    use super::*;
    use std::collections::{HashMap, HashSet};

    #[test]
    fn event_layout_and_long_sentinel() {
        assert_eq!(std::mem::size_of::<Event>(), 12);
        for len in [0usize, 1, 65534, 65535, 65536, 70000] {
            let bytes: &'static [u8] = Box::leak(format!("\"{}\",", "A".repeat(len)).into_bytes().into_boxed_slice());
            let event = Event { offset: 1, len: u16::try_from(len).unwrap_or(u16::MAX), group: 0, hash: 0 };
            assert_eq!(event_name(bytes, event), &bytes[1..1+len]);
        }
    }

    #[test]
    fn forced_fingerprint_promotion_and_cache_replacement() {
        let mut dict = OwnerDict::default();
        let mut seen = HashSet::new();
        let mut names = Vec::new();
        for i in 0..50000 { names.push(Box::leak(format!("Name{i:06}").into_bytes().into_boxed_slice()) as &'static [u8]); }
        for &name in names.iter().chain(names.iter().rev()) {
            for group in [0usize, 63, 64, 127, 240] {
                let first = seen.insert((name, group));
                assert_eq!(dict.see(name, 0, group, 4), first as i64);
            }
        }
        assert_eq!(dict.heads.get(&0), Some(&PROMOTED));
        // Same direct-cache index, distinct fingerprints, with repeated evictions.
        let one = names[0]; let two = names[1];
        let mut d = OwnerDict::default();
        for i in 0..20000 { let (n,h) = if i & 1 == 0 {(one, 7)} else {(two, 7 + CACHE_SLOTS as u64)};
            assert_eq!(d.see(n,h,0,1), i.lt(&2) as i64); }
    }

    #[test]
    fn actual_distinct_hashes_with_same_fingerprint_and_owner() {
        fn make(mut x: u64) -> Vec<u8> {
            let mut out = vec![b'A'; 12];
            for c in &mut out { x ^= x << 13; x ^= x >> 7; x ^= x << 17; *c += (x % 26) as u8; }
            out
        }
        let mut seen: HashMap<(u32,u8),u64> = HashMap::new();
        let mut found = None;
        for seed in 1..=2_000_000u64 {
            let name = make(seed.wrapping_mul(0x9e3779b97f4a7c15));
            let h = name_hash(&name);
            let owner = ((h as u128 * 48u128) >> 64) as u8;
            if let Some(&previous) = seen.get(&(h as u32, owner)) {
                let a = make(previous.wrapping_mul(0x9e3779b97f4a7c15));
                if a != name && name_hash(&a) != h { found = Some((a,name,h,owner)); break; }
            } else { seen.insert((h as u32,owner),seed); }
        }
        let (a,b,h,owner) = found.expect("expected a deterministic same-owner low32 collision");
        let ha=name_hash(&a);let hb=name_hash(&b);
        assert_ne!(ha,hb);assert_eq!(ha as u32,hb as u32);
        assert_eq!(((ha as u128*48)>>64) as u8,owner);assert_eq!(h,hb);
        let a: &'static[u8]=Box::leak(a.into_boxed_slice());let b: &'static[u8]=Box::leak(b.into_boxed_slice());
        let mut dict=OwnerDict::default();
        for n in [a,b] { assert_eq!(dict.see(n,u64::from(h as u32),3,1),1); assert_eq!(dict.see(n,u64::from(h as u32),3,1),0); }
        assert_eq!(dict.entries.len(),2);
    }
}
