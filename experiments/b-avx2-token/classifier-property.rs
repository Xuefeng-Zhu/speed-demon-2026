#![allow(dead_code)]
#[cfg(target_arch = "x86_64")]
#[target_feature(enable = "avx2")]
pub unsafe fn classify_avx2(p: *const u8) -> u32 {
    use std::arch::x86_64::*;
    let v = _mm256_loadu_si256(p.cast());
    let low = _mm256_or_si256(v, _mm256_set1_epi8(0x20));
    let alpha = _mm256_and_si256(_mm256_cmpgt_epi8(low, _mm256_set1_epi8(b'a' as i8 - 1)),
                                 _mm256_cmpgt_epi8(_mm256_set1_epi8(b'z' as i8 + 1), low));
    let digit = _mm256_and_si256(_mm256_cmpgt_epi8(v, _mm256_set1_epi8(b'0' as i8 - 1)),
                                 _mm256_cmpgt_epi8(_mm256_set1_epi8(b'9' as i8 + 1), v));
    _mm256_movemask_epi8(_mm256_or_si256(alpha, digit)) as u32
}
#[cfg(not(target_arch = "x86_64"))]
compile_error!("This test requires x86-64 and AVX2");
#[cfg(target_arch = "x86_64")]
fn reference(a: &[u8]) -> u32 {
    assert_eq!(a.len(), 32);
    a.iter().enumerate().fold(0u32, |m, (i, c)| m | (u32::from(c.is_ascii_alphanumeric()) << i))
}
#[cfg(target_arch = "x86_64")]
fn check(a: &[u8]) {
    let got = unsafe { classify_avx2(a.as_ptr()) };
    let expected = reference(a);
    assert_eq!(got, expected, "SIMD mask mismatch on {a:?}");
}
#[cfg(target_arch = "x86_64")]
fn main() {
    assert!(std::is_x86_feature_detected!("avx2"), "AVX2 is required for this test");
    // All byte values at each lane, with both alphanumeric and separator surrounding lanes.
    let mut a = [b'!'; 32];
    for fill in [b'!', b'A', 0x80, 0xff] {
        a.fill(fill);
        for i in 0..32 { for c in 0..=255u8 { let old = a[i]; a[i] = c; check(&a); a[i] = old; } }
    }
    // Cross-check mixed vector patterns, including high bytes, pseudo-randomly.
    let mut x = 0xfedc_ba98_7654_3210u64;
    for _ in 0..200_000 {
        for c in &mut a { x ^= x << 13; x ^= x >> 7; x ^= x << 17; *c = x as u8; }
        check(&a);
    }
    #[cfg(target_os = "linux")]
    unsafe {
        use std::ffi::c_void;
        unsafe extern "C" { fn getpagesize() -> i32; fn mmap(addr:*mut c_void,len:usize,prot:i32,flags:i32,fd:i32,off:i64)->*mut c_void; fn mprotect(addr:*mut c_void,len:usize,prot:i32)->i32; fn munmap(addr:*mut c_void,len:usize)->i32; }
        let page = getpagesize() as usize;
        let map = mmap(std::ptr::null_mut(), page*3, 0, 0x22, -1, 0);
        assert_ne!(map as isize, -1);
        let middle = (map as *mut u8).add(page);
        assert_eq!(mprotect(middle.cast(), page, 3), 0);
        // Both ends abut PROT_NONE guard pages. The 32-byte unaligned loads must not cross either.
        for offset in [0usize, 1, page-33, page-32] {
            let p=middle.add(offset); std::ptr::write_bytes(p, b'a', 32);
            let slice=std::slice::from_raw_parts(p, 32); check(slice);
        }
        assert_eq!(munmap(map,page*3),0);
    }
    println!("PASS AVX2 masks: 32768 byte/lane/fill cases, 200000 mixed vectors and Linux guard pages");
}
