#[cfg(target_arch = "x86_64")]
pub unsafe fn hint(dist: &[[u64; 2]], row: &[u64], i: usize) {
    if let Some(&ahead) = row.get(i + 1) {
        let next = ahead as u32 as usize;
        unsafe { std::arch::x86_64::_mm_prefetch(dist.as_ptr().add(next).cast(), std::arch::x86_64::_MM_HINT_T0); }
    }
}
