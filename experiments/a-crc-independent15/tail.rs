
#[cfg(test)]
mod independent_crc_tests {
    use super::*;
    use std::collections::HashMap;

    fn reference_hash(bytes: &[u8]) -> u64 {
        let mut h = 0u64;
        let mut chunks = bytes.chunks_exact(8);
        for chunk in &mut chunks {
            h = (h ^ u64::from_le_bytes(chunk.try_into().unwrap())).wrapping_mul(MIX);
        }
        let rest = chunks.remainder();
        let mut tail = [0u8; 8];
        tail[..rest.len()].copy_from_slice(rest);
        (h ^ u64::from_le_bytes(tail) ^ rest.len() as u64).wrapping_mul(MIX)
    }

    #[test]
    fn canonical_hash_offsets_and_lengths() {
        let mut state = 0x123456789abcdef0u64;
        let mut data = vec![0u8; 1100];
        for b in &mut data {
            state ^= state << 13;
            state ^= state >> 7;
            state ^= state << 17;
            *b = (state >> 32) as u8;
        }
        for start in 0..32 {
            for len in 0..=1024 {
                assert_eq!(original_hash(&data, start, start + len), reference_hash(&data[start..start + len]), "start={start} len={len}");
            }
        }
    }

    #[test]
    fn table_growth_preserves_id_and_collision_limit() {
        let mut bytes = Vec::new();
        let mut ranges = Vec::new();
        for i in 0..3000u32 {
            let begin = bytes.len();
            bytes.extend_from_slice(format!("/shared/endpoint/{i:08}").as_bytes());
            ranges.push((begin, bytes.len()));
        }
        bytes.extend_from_slice(&[0; 16]);
        let hash = |i: usize| {
            let mut x = i as u64 + 0x9e3779b97f4a7c15;
            x = (x ^ (x >> 30)).wrapping_mul(0xbf58476d1ce4e5b9);
            x = (x ^ (x >> 27)).wrapping_mul(0x94d049bb133111eb);
            x ^ (x >> 31)
        };
        let mut table = Table::default();
        for (i, &(s,e)) in ranges.iter().enumerate() {
            assert_eq!(table.find_bounded(&bytes, hash(i), s, e), Some(i));
        }
        for (i, &(s,e)) in ranges.iter().enumerate().rev() {
            assert_eq!(table.find_bounded(&bytes, hash(i), s, e), Some(i));
        }
        let old = std::mem::take(&mut table.names);
        table.slots.clear();
        for (i, &(_, s, e)) in old.iter().enumerate() {
            assert_eq!(table.find(&bytes, original_hash(&bytes, s, e), s, e), i);
        }
        let mut seen = HashMap::new();
        for (i, &(h,s,e)) in table.names.iter().enumerate() {
            assert_eq!(h, reference_hash(&bytes[s..e]));
            assert!(seen.insert(&bytes[s..e], i).is_none());
        }
        let mut colliding = Table::default();
        for (i, &(s,e)) in ranges.iter().take(49).enumerate() {
            assert_eq!(colliding.find_bounded(&bytes, 0, s, e), Some(i));
        }
        let (s,e) = ranges[49];
        assert_eq!(colliding.find_bounded(&bytes, 0, s, e), None);
    }
}
