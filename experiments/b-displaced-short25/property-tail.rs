#[cfg(test)]
mod displaced_tests {
    use super::*;
    fn new_plan(cap: usize) -> Plan<'static> {
        let mut p = Plan::default();
        p.slots = vec![MISS; cap.next_power_of_two()];
        p
    }
    #[test]
    fn exhaustive_short_and_absent_case() {
        let alphabet = b"abcdefghijklmnopqrstuvwxyz0123456789";
        let mut p = new_plan(1 << 18);
        let mut words = Vec::new();
        for &a in alphabet { words.push(vec![a]); for &b in alphabet {
            words.push(vec![a, b]); for &c in alphabet { words.push(vec![a, b, c]); }
        }}
        for w in &words { p.intern(w, 0); }
        p.build_short();
        assert!(!p.displaced.is_empty(), "ordinary path should actually build");
        for (id, w) in words.iter().enumerate() {
            assert_eq!(p.lookup_token(w, 0, w.len()), id as u32);
            let upper: Vec<_> = w.iter().map(u8::to_ascii_uppercase).collect();
            assert_eq!(p.lookup_token(&upper, 0, upper.len()), id as u32);
        }
        assert_eq!(p.lookup_token(b"zzzz", 0, 4), MISS);
        assert_eq!(p.lookup_token(b"", 0, 0), MISS);
    }
    #[test]
    fn same_bucket_cap_forces_exact_fallback() {
        let mut p = new_plan(2048);
        let mut selected = Vec::new();
        // 256 keys imply exactly 64 displacement groups. Deliberately put
        // at least 33 keys in one group, so capped placement must reject.
        for i in 0..1_000_000u32 {
            let w = format!("x{i:06x}");
            let h = Plan::short_hash64(key(w.as_bytes(), 0, w.len()).0[0]);
            if h as usize & 63 == 0 && selected.len() < 33 { selected.push(w); }
            if selected.len() == 33 { break; }
        }
        assert_eq!(selected.len(), 33);
        for i in 0..1_000_000u32 {
            if selected.len() == 256 { break; }
            let w = format!("y{i:06x}");
            let h = Plan::short_hash64(key(w.as_bytes(), 0, w.len()).0[0]);
            if h as usize & 63 != 0 { selected.push(w); }
        }
        for w in &selected { p.intern(w.as_bytes(), 0); }
        p.build_short();
        assert!(p.displaced.is_empty());
        for (id, w) in selected.iter().enumerate() {
            assert_eq!(p.lookup_token(w.as_bytes(), 0, w.len()), id as u32);
        }
        assert_eq!(p.lookup_token(b"nomatch", 0, 7), MISS);
    }
    #[test]
    fn rebuilding_discards_old_table_and_missing_words_remain_missing() {
        let mut p = new_plan(1024);
        for w in ["cat", "dog", "fish", "abc12345"] { p.intern(w.as_bytes(), 0); }
        p.build_short();
        assert!(!p.displaced.is_empty());
        p.intern(b"bird", 0);
        p.build_short();
        assert_eq!(p.lookup_token(b"BIRD", 0, 4), 4);
        assert_eq!(p.lookup_token(b"birdy", 0, 5), MISS);
    }
    #[test]
    fn count_cap_falls_back() {
        let mut p = new_plan(2);
        p.keys = (0..262_145u64).map(|x| Key([x + 1, 0, 0, 0])).collect();
        p.build_short();
        assert!(p.displaced.is_empty());
        assert_eq!(p.short_slots.iter().filter(|&&id| id != MISS).count(), 262_145);
    }
    #[cfg(target_os="linux")]
    #[test]
    fn guard_pages() {
        unsafe extern "C" { fn mprotect(p: *mut u8, n: usize, prot: i32) -> i32; fn munmap(p: *mut u8, n: usize) -> i32; }
        let words = ["a", "a1", "abc", "word", "words", "abc123", "abcdefg", "abcdefg1", "abcdefgh"];
        let mut p = new_plan(128);
        for w in words { p.intern(w.as_bytes(), 0); }
        p.build_short();
        unsafe {
            let base = mmap(std::ptr::null_mut(), 12288, 0, 0x22, -1, 0);
            assert_ne!(base as isize, -1); assert!(!base.is_null());
            assert_eq!(mprotect(base.add(4096), 4096, 3), 0);
            for (id, w) in words.iter().enumerate() {
                for off in [4096, 8192 - w.len()] {
                    let dst = base.add(off); std::ptr::copy_nonoverlapping(w.as_ptr(), dst, w.len());
                    let data = std::slice::from_raw_parts(dst, w.len());
                    assert_eq!(p.lookup_token(data, 0, data.len()), id as u32);
                }
            }
            assert_eq!(munmap(base, 12288), 0);
        }
    }

}
