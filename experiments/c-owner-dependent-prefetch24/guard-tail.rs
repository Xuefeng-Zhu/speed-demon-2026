#[cfg(all(test, target_os="linux", target_arch="x86_64"))]
mod guarded_prefetch_test {
    use super::*;
    extern "C" { fn mprotect(addr: *mut u8, len: usize, prot: i32) -> i32; fn sysconf(name: i32) -> isize; }
    // This deliberately leaks three mmap-backed Vecs: their storage was not allocated by Rust.
    unsafe fn tail<T>(values: &[T]) -> (*mut T, usize) where T: Copy {
        let page = sysconf(30) as usize; assert!(page >= 4096 && values.len() * std::mem::size_of::<T>() <= page);
        let base = mmap(std::ptr::null_mut(), page * 2, 3, 0x22, -1, 0);
        assert_ne!(base as isize, -1); assert!(!base.is_null());
        assert_eq!(mprotect(base.add(page), page, 0), 0);
        let ptr = base.add(page - values.len() * std::mem::size_of::<T>()).cast::<T>();
        std::ptr::copy_nonoverlapping(values.as_ptr(), ptr, values.len()); (ptr, page)
    }
    #[test]
    fn no_guard_page_access() { unsafe {
        let e = Event { offset: 0, len: 1, group: 0, hash: 0 };
        let (ep, _) = tail(&[e; 9]); let es = std::slice::from_raw_parts(ep, 9);
        let (cp, _) = tail(&[(0u64, 0usize)]); let (rp, _) = tail(&[(b"n" as &'static [u8], NONE)]); let (bp, _) = tail(&[0u64]);
        let dict = OwnerDict { cache: Vec::from_raw_parts(cp, 1, 1), entries: Vec::from_raw_parts(rp, 1, 1), bits: Vec::from_raw_parts(bp, 1, 1), ..OwnerDict::default() };
        for i in 0..=12 { prefetch_owner(&dict, es, i, 1); }
        // Overflow in row * words or group-word offset must not construct a pointer.
        prefetch_owner(&dict, es, 0, usize::MAX);
        std::mem::forget(dict);
    }}
}
