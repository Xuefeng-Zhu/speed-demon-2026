#[cfg(test)]
mod compact_tests {
    use super::*;
    fn plan(n:usize) -> Plan<'static> {
        let mut p = Plan::default();
        p.keys = (0..n).map(|i| {
            let text = format!("x{:07x}", i);
            key(text.as_bytes(), 0, text.len())
        }).collect();
        p.build_short();
        p
    }
    #[test]
    fn exact_and_capacity_boundary() {
        for n in [0,1,255,4096,262_144,262_145] {
            let p = plan(n);
            assert_eq!(p.short_keys.len(), if n <= 262_144 {n} else {0});
            for i in (0..n).step_by((n/1000).max(1)) {
                let lower=format!("x{:07x}",i); let upper=lower.to_ascii_uppercase();
                assert_eq!(p.lookup_token(lower.as_bytes(),0,8), i as u32);
                assert_eq!(p.lookup_token(upper.as_bytes(),0,8), i as u32);
            }
            assert_eq!(p.lookup_token(b"z1234567",0,8),MISS);
        }
    }
    #[test]
    fn collision_empty_and_long() {
        let mut p=Plan::default(); p.slots=vec![MISS;8192];
        for term in [b"A".as_slice(),b"a1",b"ABCD1234",b"LongToken9",b"0123456789abcdef",b"a2345678901234567890123456789012"] {
            p.intern(term,IN_BOOL);
        }
        p.build_short();
        for term in [b"a".as_slice(),b"A1",b"abcd1234",b"longtoken9",b"0123456789abcdef",b"A2345678901234567890123456789012"] {
            assert_ne!(p.lookup_token(term,0,term.len()),MISS);
        }
        assert_eq!(p.lookup_token(b"a2345678",0,8),MISS);
    }
}
