#[cfg(all(test, target_os="linux", target_arch="x86_64", target_feature="avx2"))]
mod avx2_guard {
    use super::*;
    use std::ffi::c_void;
    extern "C" {
        fn mprotect(addr: *mut c_void, len: usize, prot: i32) -> i32;
        fn munmap(addr: *mut c_void, len: usize) -> i32;
        fn sysconf(name: i32) -> isize;
    }
    #[test]
    fn group_load_at_protected_page_edges() {
        assert!(std::arch::is_x86_feature_detected!("avx2"));
        let page = unsafe { sysconf(30) } as usize; // Linux _SC_PAGESIZE
        assert!(page >= 4096 && page.is_power_of_two());
        assert_eq!(std::mem::size_of::<ShortGroup>(),64);
        let p = unsafe { mmap(std::ptr::null_mut(), page*3, 3, 0x22, -1, 0) } as *mut u8;
        assert_ne!(p as isize,-1);
        unsafe {
            assert_eq!(mprotect(p.cast(),page,0),0);
            assert_eq!(mprotect(p.add(page*2).cast(),page,0),0);
            for ptr in [p.add(page),p.add(page*2-64)] {
                assert_eq!((ptr as usize)&63,0);
                let group=ptr.cast::<ShortGroup>();
                let mut seed=1u64;
                for iter in 0..100_000u64 {
                    let mut keys=[0u64;4];
                    for k in &mut keys { seed ^= seed << 13; seed ^= seed >> 7; seed ^= seed << 17; *k=seed; }
                    if iter % 3 == 0 { keys[(iter as usize)%4]=0; }
                    group.write(ShortGroup { keys, ids: [0,1,2,3] });
                    let q=if iter%2==0 { keys[(iter as usize/2)%4] } else { seed ^ 0x9e3779b97f4a7c15 };
                    let expected=keys.iter().enumerate().fold(0,|m,(i,&x)| m | (u32::from(x==q)<<i));
                    assert_eq!(matching(&*group,q),expected);
                    let zero=keys.iter().enumerate().fold(0,|m,(i,&x)| m | (u32::from(x==0)<<i));
                    assert_eq!(matching(&*group,0),zero);
                }
            }
            assert_eq!(munmap(p.cast(),page*3),0);
        }
    }
}
