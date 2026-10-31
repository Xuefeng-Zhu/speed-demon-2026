#[cfg(all(test, any(all(target_arch="x86_64", target_feature="bmi2"), b_portable_pext)))]
mod direct_exact {
    use super::*;
    #[test]
    fn exhaust_all_legal_four_byte_encodings() {
        let alphabet=b"0123456789abcdefghijklmnopqrstuvwxyz";
        let mut seen=vec![false;1<<24];
        let mut count=0usize;
        for len in 1..=4 {
            let total=36usize.pow(len as u32);
            for mut v in 0..total {
                let mut key=0u64;
                for byte in 0..len { key |= u64::from(alphabet[v%36]) << (byte*8); v/=36; }
                let index=direct_index(key);
                assert!(index<seen.len());
                assert!(!seen[index],"collision len={len} key={key:x} index={index}");
                seen[index]=true; count+=1;
            }
        }
        assert_eq!(count,1_727_604);
        println!("PASS {count} distinct alphanumeric 1–4-byte encodings");
    }
}
#[cfg(all(test, target_os="linux", target_arch="x86_64", target_feature="bmi2"))]
mod bmi2_guard {
    use super::*;
    use std::ffi::c_void;
    extern "C" {
        fn mprotect(addr:*mut c_void,len:usize,prot:i32)->i32;
        fn munmap(addr:*mut c_void,len:usize)->i32;
        fn sysconf(name:i32)->isize;
    }
    #[test]
    fn direct_lookup_at_protected_page_end() {
        assert!(std::arch::is_x86_feature_detected!("bmi2"));
        let page=unsafe{sysconf(30)} as usize;
        assert!(page>=4096 && page.is_power_of_two());
        let ptr=unsafe{mmap(std::ptr::null_mut(),page*3,3,0x22,-1,0)} as *mut u8;
        assert_ne!(ptr as isize,-1);
        unsafe {
            assert_eq!(mprotect(ptr.cast(),page,0),0);
            assert_eq!(mprotect(ptr.add(page*2).cast(),page,0),0);
            let mut plan=Plan{slots:vec![MISS;64],..Default::default()};
            let words:[&[u8];9]=[b"a",b"09",b"the",b"zzzz",b"7p0z",b"abcde",b"abcdefg",b"abcdefgh",b"abcdefghi"];
            let ids:Vec<_>=words.iter().map(|w|plan.intern(w,IN_BOOL)).collect();
            plan.build_short();
            for (word,&id) in words.iter().zip(&ids) {
                for offset in [page, page*2-word.len()] {
                    let dst=ptr.add(offset);
                    std::ptr::copy_nonoverlapping(word.as_ptr(),dst,word.len());
                    let slice=std::slice::from_raw_parts(dst,word.len());
                    assert_eq!(plan.lookup_token(slice,0,word.len()),id);
                }
            }
            for word in [b"0".as_slice(),b"zz".as_slice(),b"xyz".as_slice(),b"zzzx".as_slice()] {
                let dst=ptr.add(page*2-word.len());
                std::ptr::copy_nonoverlapping(word.as_ptr(),dst,word.len());
                let slice=std::slice::from_raw_parts(dst,word.len());
                assert_eq!(plan.lookup_token(slice,0,word.len()),MISS);
            }
            assert_eq!(munmap(ptr.cast(),page*3),0);
        }
    }
}
