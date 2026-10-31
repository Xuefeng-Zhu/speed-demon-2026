#[cfg(test)]
mod independent_direct_tests {
    use super::*;

    const ALPHABET: &[u8] = b"abcdefghijklmnopqrstuvwxyz0123456789";

    fn case_variants(word: &[u8]) -> Vec<Vec<u8>> {
        (0..(1usize << word.len().min(2))).map(|mask| {
            word.iter().enumerate().map(|(i, &b)| {
                if mask & (1 << i) != 0 && b.is_ascii_lowercase() { b.to_ascii_uppercase() } else { b }
            }).collect()
        }).collect()
    }

    #[test]
    fn all_short_keys_present_absent_and_mixed_case() {
        let mut all = Vec::<Vec<u8>>::new();
        for &a in ALPHABET {
            all.push(vec![a]);
            for &b in ALPHABET { all.push(vec![a, b]); }
        }
        assert_eq!(all.len(), 36 + 36 * 36);
        for subset in 0..2 {
            let mut plan = Plan { slots: vec![MISS; 8192], ..Default::default() };
            let mut ids = vec![MISS; all.len()];
            for (i, key) in all.iter().enumerate() {
                if subset == 0 || i % 3 == 0 { ids[i] = plan.intern(key, IN_BOOL); }
            }
            let extra = [b"abc".as_slice(), b"abcdefgh", b"abcdefghi", b"abcdefghijklmnopqrstuvwxyz012345"];
            let extra_ids: Vec<_> = extra.iter().map(|s| plan.intern(s, IN_BOOL)).collect();
            plan.build_short();
            assert_eq!(plan.tiny_slots.len(), 1 << 16);
            for (i, key) in all.iter().enumerate() {
                for case in case_variants(key) {
                    assert_eq!(plan.lookup_token(&case, 0, case.len()), ids[i], "{case:?}");
                    for offset in 0..65 {
                        let mut buf = vec![b'!'; offset];
                        buf.extend_from_slice(&case);
                        assert_eq!(plan.lookup_token(&buf, offset, case.len()), ids[i]);
                    }
                }
            }
            for (key, &id) in extra.iter().zip(&extra_ids) {
                assert_eq!(plan.lookup_token(key, 0, key.len()), id);
            }
            assert_eq!(plan.lookup_token(&[], 0, 0), MISS);
        }
        let mut empty = Plan { slots: vec![MISS], ..Default::default() };
        empty.build_short();
        for key in [b"a".as_slice(), b"A1", b"123", b"abcdefgh", b"abcdefghi"] {
            assert_eq!(empty.lookup_token(key, 0, key.len()), MISS);
        }
        assert_eq!(empty.lookup_token(&[], 0, 0), MISS);
    }

    #[cfg(unix)]
    #[test]
    fn guard_page_both_ends() {
        unsafe extern "C" {
            fn getpagesize() -> i32;
            fn mprotect(addr: *mut u8, len: usize, prot: i32) -> i32;
            fn munmap(addr: *mut u8, len: usize) -> i32;
        }
        #[cfg(target_os = "macos")]
        const MAP_ANON: i32 = 0x1000;
        #[cfg(not(target_os = "macos"))]
        const MAP_ANON: i32 = 0x20;
        let keys: [&[u8]; 5] = [b"a", b"ab", b"abc", b"abcdefgh", b"abcdefghi"];
        let mut plan = Plan { slots: vec![MISS; 64], ..Default::default() };
        let ids: Vec<_> = keys.iter().map(|s| plan.intern(s, IN_BOOL)).collect();
        plan.build_short();
        unsafe {
            let page = getpagesize() as usize;
            let base = mmap(std::ptr::null_mut(), page * 3, 3, 2 | MAP_ANON, -1, 0);
            assert_ne!(base as isize, -1);
            assert!(!base.is_null());
            assert_eq!(mprotect(base, page, 0), 0);
            assert_eq!(mprotect(base.add(2 * page), page, 0), 0);
            for (key, &id) in keys.iter().zip(&ids) {
                for at in [base.add(page), base.add(2 * page - key.len())] {
                    std::ptr::copy_nonoverlapping(key.as_ptr(), at, key.len());
                    let slice = std::slice::from_raw_parts(at, key.len());
                    assert_eq!(plan.lookup_token(slice, 0, slice.len()), id);
                }
            }
            assert_eq!(munmap(base, page * 3), 0);
        }
    }
}
