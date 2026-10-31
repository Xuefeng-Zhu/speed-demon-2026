#[cfg(all(test, any(all(target_arch="x86_64", target_feature="bmi2"), b_portable_pext)))]
mod direct_exact {
    use super::*;
    #[test]
    fn direct_allocation_and_case() {
        let mut empty=Plan{slots:vec![MISS;64],..Default::default()};
        empty.build_short();
        assert_eq!(empty.short_direct.len(),0);
        assert_eq!(empty.lookup_token(b"",0,0),MISS);
        assert_eq!(empty.lookup_token(b"x",0,1),MISS);
        let mut long_only=Plan{slots:vec![MISS;64],..Default::default()};
        let long_id=long_only.intern(b"abcd",IN_BOOL);
        long_only.build_short();
        assert_eq!(long_only.short_direct.len(),0);
        assert_eq!(long_only.lookup_token(b"ABC",0,3),MISS);
        assert_eq!(long_only.lookup_token(b"ABCD",0,4),long_id);
        let mut plan=Plan{slots:vec![MISS;64],..Default::default()};
        let terms: [&[u8];6]=[b"0",b"a",b"AZ",b"z9",b"The",b"9ZZ"];
        let ids:Vec<_>=terms.iter().map(|t|plan.intern(t,IN_BOOL)).collect();
        plan.build_short();
        assert_eq!(plan.short_direct.len(),1<<18);
        assert_eq!(plan.lookup_token(b"",0,0),MISS);
        for (t,id) in terms.iter().zip(ids) {
            assert_eq!(plan.lookup_token(t,0,t.len()),id);
            assert_eq!(plan.lookup_token(&t.to_ascii_uppercase(),0,t.len()),id);
            assert_eq!(plan.lookup_token(&t.to_ascii_lowercase(),0,t.len()),id);
        }
        for t in [b"1".as_slice(),b"ab",b"zzz"] { assert_eq!(plan.lookup_token(t,0,t.len()),MISS); }
    }
    #[test]
    fn exhaust_all_legal_three_byte_encodings() {
        let alphabet=b"0123456789abcdefghijklmnopqrstuvwxyz";
        let mut seen=vec![false;1<<18];
        let mut count=0usize;
        for len in 1..=3 {
            let total=36usize.pow(len as u32);
            for mut v in 0..total {
                let mut key=0u64;
                for byte in 0..len { key |= u64::from(alphabet[v%36]) << (byte*8); v/=36; }
                let index=direct_index(key);
                assert!(index<seen.len());
                assert!(!seen[index],"collision len={len} key={key:x} index={index}");
                let lower=key.to_le_bytes();
                let upper=lower[..len].to_ascii_uppercase();
                assert_eq!(direct_index(super::key(&upper,0,len).0[0]),index);
                seen[index]=true; count+=1;
            }
        }
        assert_eq!(count,47_988);
        println!("PASS {count} distinct alphanumeric 1–3-byte encodings");
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
