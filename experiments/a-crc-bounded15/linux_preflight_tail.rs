#[cfg(test)]
mod linux_crc_preflight {
    use super::*;
    #[cfg(not(all(target_arch = "x86_64", target_feature = "sse4.2")))]
    compile_error!("Preflight must compile the real x86-64 SSE4.2 CRC path");
    extern "C" { fn mprotect(addr: *mut u8, len: usize, prot: i32) -> i32; fn munmap(addr: *mut u8, len: usize) -> i32; }
    fn software_crc32c(mut c: u32, w: u64) -> u32 {
        for byte in w.to_le_bytes() {
            c ^= byte as u32;
            for _ in 0..8 { c = (c >> 1) ^ (0x82f6_3b78 & 0u32.wrapping_sub(c & 1)); }
        }
        c
    }
    #[test]
    fn real_crc_instruction_and_guarded_page() {
        assert!(std::is_x86_feature_detected!("sse4.2"), "SSE4.2 unavailable");
        let mut x = 0x6a09e667f3bcc909u64;
        for _ in 0..100_000 {
            x ^= x << 13; x ^= x >> 7; x ^= x << 17;
            let h = x.rotate_left(27);
            assert_eq!(fast_mix(h, x), (software_crc32c((h >> 32) as u32, x) as u64) << 32);
        }
        unsafe {
            // The second page is inaccessible; accesses beyond the first page fault.
            let p = mmap(std::ptr::null_mut(), 8192, 3, 0x22, -1, 0);
            assert_ne!(p as isize, -1, "mmap failed");
            for i in 0..4096 { *p.add(i) = (i as u8).wrapping_mul(17); }
            assert_eq!(mprotect(p.add(4096), 4096, 0), 0, "mprotect failed");
            let d = std::slice::from_raw_parts(p, 4096);
            for end in 4000..=4088 {
                for len in 0..=64 {
                    let start = end - len;
                    let mut h = 0u64;
                    for chunk in d[start..end].chunks_exact(8) {
                        h = (h ^ u64::from_le_bytes(chunk.try_into().unwrap())).wrapping_mul(MIX);
                    }
                    let rest = &d[start + len / 8 * 8..end];
                    let mut tail = [0; 8]; tail[..rest.len()].copy_from_slice(rest);
                    h = (h ^ u64::from_le_bytes(tail) ^ rest.len() as u64).wrapping_mul(MIX);
                    assert_eq!(original_hash(d, start, end), h);
                }
            }
            assert_eq!(munmap(p, 8192), 0);
        }
        println!("CRC32C_HARDWARE_AND_GUARD_PAGE_PASS");
    }
}
