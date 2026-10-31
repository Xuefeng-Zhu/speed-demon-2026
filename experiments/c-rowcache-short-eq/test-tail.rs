
#[cfg(test)]
mod row_eq_tests {
    use super::*;
    use std::collections::HashSet;

    #[test]
    fn all_lengths_alignments_and_each_difference() {
        let mut a = vec![0u8; 400];
        let mut b = vec![0u8; 400];
        for (i, x) in a.iter_mut().enumerate() { *x = (i as u8).wrapping_mul(73).wrapping_add(19); }
        for n in 0..=256 {
            for offset in 0..=31 {
                let aa = &a[offset..offset+n];
                let boffset = (31-offset) % 32;
                b[boffset..boffset+n].copy_from_slice(aa);
                let bb = &mut b[boffset..boffset+n];
                assert!(row_name_equal(aa, bb), "equal len={n} offset={offset}");
                for k in 0..n {
                    bb[k] ^= 1;
                    assert!(!row_name_equal(aa, bb), "difference len={n} offset={offset} k={k}");
                    bb[k] ^= 1;
                }
                if n < 256 { assert!(!row_name_equal(aa, &b[boffset..boffset+n+1])); }
            }
        }
    }

    unsafe fn guarded(data: &[u8], at_end: bool) -> (*mut u8, usize, &'static [u8]) {
        unsafe extern "C" { fn getpagesize() -> i32; fn mprotect(addr: *mut u8, len: usize, prot: i32) -> i32; }
        let page = unsafe { getpagesize() as usize };
        let flags = 2 | if cfg!(target_os = "macos") { 0x1000 } else { 0x20 };
        let ptr = unsafe { mmap(std::ptr::null_mut(), page * 3, 3, flags, -1, 0) };
        assert_ne!(ptr as isize, -1);
        assert_eq!(unsafe { mprotect(ptr, page, 0) }, 0);
        assert_eq!(unsafe { mprotect(ptr.add(2 * page), page, 0) }, 0);
        let start = unsafe { ptr.add(page + if at_end { page - data.len() } else { 0 }) };
        unsafe { std::ptr::copy_nonoverlapping(data.as_ptr(), start, data.len()); }
        (ptr, page, unsafe { std::slice::from_raw_parts(start, data.len()) })
    }

    #[test]
    fn protected_page_boundaries() {
        unsafe extern "C" { fn munmap(addr: *mut u8, len: usize) -> i32; }
        for n in 0..=32 {
            let data: Vec<u8> = (0..n).map(|i| (i as u8).wrapping_mul(47).wrapping_add(5)).collect();
            for a_end in [false,true] { for b_end in [false,true] {
                let (ap,pa,a) = unsafe { guarded(&data,a_end) };
                let (bp,pb,b) = unsafe { guarded(&data,b_end) };
                assert!(row_name_equal(a,b));
                assert_eq!(unsafe { munmap(bp,pb*3) },0);
                for k in 0..n {
                    let mut changed = data.clone(); changed[k] ^= 1;
                    let (cp,pc,c) = unsafe { guarded(&changed,b_end) };
                    assert!(!row_name_equal(a,c), "n={n} k={k}");
                    assert_eq!(unsafe { munmap(cp,pc*3) },0);
                }
                assert_eq!(unsafe { munmap(ap,pa*3) },0);
            }}
        }
    }

    #[test]
    fn forced_hash_collision_and_group_model() {
        let names: Vec<&'static [u8]> = (0..1000).map(|i| {
            let n = 3 + i%29;
            let mut v = vec![(i%251) as u8;n];
            v[..3].copy_from_slice(&(i as u32).to_le_bytes()[..3]);
            Box::leak(v.into_boxed_slice()) as &'static [u8]
        }).collect();
        let mut dict = OwnerDict::default();
        let mut seen = HashSet::<(usize,usize)>::new();
        for k in 0..150_000usize {
            let i = (k*619 + k/1000) % names.len();
            let g = (k*113 + k/97) % 257;
            let expected = seen.insert((i,g)) as i64;
            let got = dict.see(names[i], 0, g, 257_usize.div_ceil(64));
            assert_eq!(got, expected, "name={i} group={g}");
            assert_eq!(dict.see(names[i], 0, g, 257_usize.div_ceil(64)), 0);
        }
    }
}
