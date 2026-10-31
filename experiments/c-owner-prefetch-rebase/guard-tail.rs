#[cfg(test)]
mod prefetch_checks {
    use super::*;
    #[test]
    fn slice_edges_and_cache_lengths() {
        let bytes = [7u8; 33];
        let short = [(0u64, 0usize); 1];
        let full = vec![(0u64, 0usize); CACHE_SLOTS];
        for &offset in &[0u32, 1, 7, 8, 31, 32, 33, u32::MAX] {
            for &hash in &[0u64, 1, (CACHE_SLOTS - 1) as u64, u64::MAX] {
                let e = Event { offset, len: 0, group: 0, hash };
                prefetch_future(&bytes, &[], &e);
                prefetch_future(&bytes, &short, &e);
                prefetch_future(&bytes, &full, &e);
            }
        }
    }
    #[cfg(all(target_arch = "x86_64", target_os = "linux"))]
    #[test]
    fn linux_guard_pages() {
        unsafe extern "C" {
            fn sysconf(name: i32) -> isize;
            fn mprotect(addr: *mut u8, len: usize, prot: i32) -> i32;
            fn munmap(addr: *mut u8, len: usize) -> i32;
        }
        unsafe {
            let page = sysconf(30) as usize;
            assert!(page >= 1024 && page.is_power_of_two());
            let mem = mmap(std::ptr::null_mut(), 2*page, 3, 0x22, -1, 0);
            assert_ne!(mem as isize, -1);
            assert_eq!(mprotect(mem.add(page), page, 0), 0);
            let bytes = std::slice::from_raw_parts(mem, page);
            let data = Event {offset: (page-1) as u32, len: 1, group: 0, hash: 0};
            let end = Event {offset: page as u32, len: 0, group: 0, hash: u64::MAX};
            let cache_bytes = CACHE_SLOTS * std::mem::size_of::<(u64, usize)>();
            assert_eq!(cache_bytes % page, 0);
            let cm = mmap(std::ptr::null_mut(), cache_bytes+page, 3, 0x22, -1, 0);
            assert_ne!(cm as isize, -1);
            assert_eq!(mprotect(cm.add(cache_bytes), page, 0), 0);
            let cache = std::slice::from_raw_parts(cm.cast::<(u64,usize)>(), CACHE_SLOTS);
            for _ in 0..1000 { prefetch_future(bytes, cache, &data); prefetch_future(bytes, cache, &end); }
            assert_eq!(munmap(cm, cache_bytes+page), 0);
            assert_eq!(munmap(mem, 2*page), 0);
        }
    }
}
