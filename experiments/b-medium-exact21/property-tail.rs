
#[cfg(test)]
mod medium_tests {
    use super::*;
    #[test]
    fn lookup_exact_across_lengths_and_alignments() {
        let mut p = Plan { slots: vec![MISS; 1 << 16], ..Default::default() };
        let mut words = Vec::new();
        for n in 1..=32usize {
            for i in 0..300u64 {
                let seed = i.wrapping_mul(0x9e3779b97f4a7c15).rotate_left(n as u32);
                let mut x = seed;
                let mut word = Vec::new();
                for _ in 0..n { x ^= x << 13; x ^= x >> 7; x ^= x << 17; word.push(b'a' + (x % 26) as u8); }
                p.intern(&word, IN_BOOL);
                words.push(word);
            }
        }
        p.build_short(); p.build_medium();
        #[cfg(medium_forced)] assert!(p.medium_slots.is_empty(), "forced collisions must activate fallback");
        for word in words {
            let expected = p.slot(&key(&word, 0, word.len())).1;
            for offset in [0,1,7,15,31] {
                let mut b = vec![b'.'; offset]; b.extend(word.iter().map(|c| c.to_ascii_uppercase()));
                assert_eq!(p.lookup_token(&b, offset, word.len()), expected);
                b.extend_from_slice(b"---padding-to-force-direct-load-1234567890");
                assert_eq!(p.lookup_token(&b, offset, word.len()), expected);
            }
        }
        for n in 1..=32 {
            let absent = vec![b'9'; n];
            assert_eq!(p.lookup_token(&absent, 0, n), p.slot(&key(&absent, 0, n)).1);
        }
        let mut empty = Plan { slots: vec![MISS; 1], ..Default::default() };
        empty.build_short(); empty.build_medium();
        assert_eq!(empty.lookup_token(b"abcdefghijklmno", 0, 15), MISS);
    }
}
