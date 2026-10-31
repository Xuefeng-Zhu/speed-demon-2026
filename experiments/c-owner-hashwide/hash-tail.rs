#[cfg(test)]
mod hash_review {
    use super::*;
    #[test]
    fn offsets_lengths_and_random_content_match() {
        let mut x=0x239ea63d79ab2341u64;
        for len in 0..=1024usize { for off in 0..32usize {
            let mut bytes=vec![0u8;len+off];
            for b in &mut bytes {x^=x<<13;x^=x>>7;x^=x<<17;*b=x as u8;}
            let s=&bytes[off..];
            assert_eq!(name_hash(s),BuildHasherDefault::<Fx>::default().hash_one(s),"{len} {off}");
        }}
        for len in [65534usize,65535,65536,131072,1_000_000] {
            let s:Vec<u8>=(0..len).map(|i| (i.wrapping_mul(37) as u8)).collect();
            assert_eq!(name_hash(&s),BuildHasherDefault::<Fx>::default().hash_one(s.as_slice()));
        }
    }
}
