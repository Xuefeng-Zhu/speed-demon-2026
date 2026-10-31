#[cfg(test)]
mod property_tests {
    use super::bucket_min;
    #[test]
    fn all_unsigned_minima() {
        let mut state=0x9126ab5de4327651u64;
        let mut comparisons=0usize;
        for len in 1..=513 {
            for pattern in 0..32 {
                let mut v=Vec::with_capacity(len+3);
                for i in 0..len+3 {
                    state ^= state<<13; state ^= state>>7; state ^= state<<17;
                    let k=match pattern%8 {0=>u64::MAX,1=>0,2=>1u64<<63,3=>(1u64<<63)-1,4=>i as u64,5=>u64::MAX-i as u64,_=>state};
                    v.push((k,(state>>32) as u32));
                }
                for offset in 0..=3 {
                    let x=&v[offset..offset+len];
                    assert_eq!(bucket_min(x),x.iter().map(|e|e.0).min().unwrap(),"len={len} pattern={pattern} offset={offset}");
                    comparisons+=1;
                }
            }
        }
        assert_eq!(comparisons,65664);
    }
    #[cfg(target_os="linux")]
    #[test]
    fn protected_page_boundaries() {
        use std::ffi::c_void;
        unsafe extern "C" {fn getpagesize()->i32; fn mprotect(addr:*mut c_void,len:usize,prot:i32)->i32;fn munmap(addr:*mut c_void,len:usize)->i32;}
        let page=unsafe{getpagesize()} as usize;
        assert_eq!(std::mem::size_of::<(u64,u32)>(),16);
        unsafe {
            let raw=super::mmap(std::ptr::null_mut(),page*3,0,2|0x20,-1,0);
            assert_ne!(raw as isize,-1); let middle=raw.add(page);
            assert_eq!(mprotect(middle.cast(),page,1|2),0);
            for n in 1..=128usize {
                for shift in [0usize,8] {
                    let p=middle.add(page-shift-n*16).cast::<(u64,u32)>();
                    for i in 0..n {std::ptr::write(p.add(i),((n-i) as u64,i as u32));}
                    let s=std::slice::from_raw_parts(p,n);
                    assert_eq!(bucket_min(s),1,"n={n} shift={shift}");
                }
            }
            assert_eq!(munmap(raw.cast(),page*3),0);
        }
    }
}
