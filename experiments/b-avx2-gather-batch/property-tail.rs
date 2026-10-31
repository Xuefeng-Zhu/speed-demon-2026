
#[cfg(test)]
mod gather_batch_tests {
    use super::*;
    fn plan_for(words: &[Vec<u8>]) -> Plan<'static> {
        let mut plan = Plan { slots: vec![MISS; 8192], ..Default::default() };
        for w in words { plan.intern(w, IN_BOOL); }
        plan.build_short();
        plan
    }
    fn compare(plan: &Plan, data: &[u8], spans: &[(usize, usize)]) {
        let mut expected = Vec::new();
        let mut actual = Vec::new();
        let mut batch = WordBatch::default();
        for &(s, e) in spans {
            push_word(data, s, e, plan, &mut expected);
            batch.push(data, s, e, plan, &mut actual);
        }
        batch.flush(data, plan, &mut actual);
        assert_eq!(actual, expected, "spans={spans:?}");
        assert_eq!(batch.len, 0);
    }
    fn next(r: &mut u64) -> u64 {
        *r = r.wrapping_mul(6364136223846793005).wrapping_add(1442695040888963407);
        *r
    }
    #[test]
    fn mixed_lengths_empty_tables_and_probes() {
        let mut rng = 7;
        let mut words = Vec::new();
        for n in 1..=32 {
            for _ in 0..16 {
                let w: Vec<u8> = (0..n).map(|_| b'a' + (next(&mut rng) % 26) as u8).collect();
                words.push(w);
            }
        }
        let plan = plan_for(&words);
        let empty = plan_for(&[]);
        let long_only = plan_for(&[b"longerthan8".to_vec()]);
        for size in 0..=33 {
            for round in 0..1500 {
                let mut data = Vec::new();
                let mut spans = Vec::new();
                for i in 0..size {
                    let start = data.len();
                    let idx = (next(&mut rng) as usize) % words.len();
                    let mut word = words[idx].clone();
                    if (round + i) % 3 == 0 { word[0] = word[0].to_ascii_uppercase(); }
                    if (round + i) % 5 == 0 { word[0] = b'0' + (next(&mut rng) % 10) as u8; }
                    if (round + i) % 19 == 0 { word.resize(40, b'z'); }
                    data.extend_from_slice(&word);
                    spans.push((start, data.len()));
                    data.push(b' ');
                }
                compare(&plan, &data, &spans);
                compare(&empty, &data, &spans);
                compare(&long_only, &data, &spans);
            }
        }
    }
    #[test]
    fn batches_flush_in_order_and_collision_fallback() {
        let mut words = Vec::new();
        for i in 0..1024 { words.push(format!("x{i:04}").into_bytes()); }
        let plan = plan_for(&words);
        let mut data = Vec::new(); let mut spans = Vec::new();
        for (i, word) in words.iter().enumerate() {
            let s = data.len(); data.extend_from_slice(word);
            spans.push((s, data.len())); data.push(b' ');
            if i % 7 == 0 { compare(&plan, &data, &spans); spans.clear(); }
        }
        compare(&plan, &data, &spans);
    }
    #[cfg(all(target_arch = "x86_64", target_feature = "avx2"))]
    #[test]
    fn target_has_real_avx2() { assert!(std::arch::is_x86_feature_detected!("avx2")); }

    #[cfg(any(target_os = "linux", target_os = "macos"))]
    extern "C" {
        fn getpagesize() -> i32;
        fn mprotect(p: *mut u8, n: usize, prot: i32) -> i32;
        fn munmap(p: *mut u8, n: usize) -> i32;
    }
    #[cfg(any(target_os = "linux", target_os = "macos"))]
    unsafe fn guard_mapping() -> (*mut u8, usize) {
        let page = getpagesize() as usize;
        #[cfg(target_os = "linux")] let anon = 0x20;
        #[cfg(target_os = "macos")] let anon = 0x1000;
        let p = mmap(std::ptr::null_mut(), page * 3, 3, 2 | anon, -1, 0);
        assert_ne!(p as isize, -1);
        assert_eq!(mprotect(p, page, 0), 0);
        assert_eq!(mprotect(p.add(page * 2), page, 0), 0);
        (p, page)
    }
    #[cfg(any(target_os = "linux", target_os = "macos"))]
    #[test]
    fn token_slices_touch_protected_pages() {
        unsafe {
            let (map, page) = guard_mapping();
            let body = std::slice::from_raw_parts_mut(map.add(page), page);
            let plan = plan_for(&[b"a".to_vec(), b"abcdefgh".to_vec(), b"longerthan8".to_vec()]);
            let empty = plan_for(&[]);
            let long_only = plan_for(&[b"longerthan8".to_vec()]);
            for n in 1..=40 {
                for s in [0, page - n] {
                    body.fill(b'!');
                    body[s..s+n].fill(b'a');
                    let spans = [(s, s+n); 4];
                    compare(&plan, body, &spans);
                    compare(&empty, body, &spans);
                    compare(&long_only, body, &spans);
                }
            }
            assert_eq!(munmap(map, page * 3), 0);
        }
    }
    #[cfg(all(target_os = "linux", target_arch = "x86_64", target_feature = "avx2"))]
    #[test]
    fn target_gather_sanitizes_miss_at_guarded_tables() {
        unsafe {
            let (smap, page) = guard_mapping();
            let (kmap, kpage) = guard_mapping();
            assert_eq!(page, kpage);
            for right in [false, true] {
                let s = if right { smap.add(2*page - 16) } else { smap.add(page) };
                let k = if right { kmap.add(2*page - 32) } else { kmap.add(page) };
                let sp = s.cast::<u32>();
                sp.add(0).write(0); sp.add(1).write(MISS);
                sp.add(2).write(0); sp.add(3).write(MISS);
                let kp = k.cast::<Key>();
                kp.write(Key([0x1234_5678, 0, 0, 0]));
                let slots = std::slice::from_raw_parts(sp, 4);
                let keys = std::slice::from_raw_parts(kp, 1);
                let (ids, values) = gather_initial(slots, keys, [0,1,2,3], [true,true,false,true]);
                assert_eq!(ids, [0,MISS,0,MISS]);
                assert_eq!(values, [0x1234_5678; 4]);
                let (ids, values) = gather_initial(slots, keys, [1,3,1,3], [true; 4]);
                assert_eq!(ids, [MISS; 4]);
                assert_eq!(values, [0x1234_5678; 4]);
                let (_, values) = gather_initial(slots, keys, [1,3,1,3], [false; 4]);
                assert_eq!(values, [0x1234_5678; 4]);
            }
            assert_eq!(munmap(smap, page * 3), 0);
            assert_eq!(munmap(kmap, page * 3), 0);
        }
    }
}
