#[cfg(test)]
mod batch_tests {
    use super::*;
    fn setup() -> Plan<'static> {
        let mut plan = Plan { slots: vec![MISS; 512], ..Default::default() };
        for n in 1..=32 { plan.intern(&vec![b'a'; n], 0); }
        plan.intern(b"0", 0);
        plan.intern(b"007", 0);
        plan.intern(b"z9z9z9z9", 0);
        plan.build_short();
        plan
    }
    #[test]
    fn batch_matches_individual_with_present_absent_and_collisions() {
        let p = setup();
        for total in 0..=65 {
            let mut data = Vec::new(); let mut ranges = Vec::new();
            for i in 0..total {
                let n = 1 + (i * 19 % 37); let start = data.len();
                let byte = if i % 5 == 0 { b'Z' } else if i % 3 == 0 { b'A' } else { b'a' };
                data.extend(std::iter::repeat(byte).take(n)); ranges.push((start, data.len())); data.push(b'!');
            }
            let mut actual = Vec::new(); resolve_batch(&data, &p, &ranges, &mut actual);
            let expected: Vec<_> = ranges.iter().map(|&(a,b)| if b-a <= 32 {p.lookup_token(&data,a,b-a)} else { MISS }).collect();
            assert_eq!(actual, expected, "length {total}");
        }
    }
    #[cfg(target_os = "linux")]
    #[test]
    fn mapped_boundaries_next_to_guard_pages() {
        use std::ffi::c_void;
        unsafe extern "C" {fn getpagesize()->i32; fn mmap(a:*mut c_void,n:usize,p:i32,f:i32,fd:i32,o:i64)->*mut c_void; fn mprotect(a:*mut c_void,n:usize,p:i32)->i32; fn munmap(a:*mut c_void,n:usize)->i32;}
        unsafe {
            let page=getpagesize() as usize;
            let map=mmap(std::ptr::null_mut(),page*3,0,0x22,-1,0);
            assert_ne!(map as isize,-1); let middle=(map as *mut u8).add(page);
            assert_eq!(mprotect(middle.cast(),page,3),0);
            let p=setup();
            for n in 1..=37 {
                for offset in [0,page-n] {
                    let ptr=middle.add(offset); std::ptr::write_bytes(ptr,b'A',n);
                    let data=std::slice::from_raw_parts(ptr,n);
                    let ranges=vec![(0,n);17]; let mut actual=Vec::new();
                    resolve_batch(data,&p,&ranges,&mut actual);
                    let id=if n<=32 {p.lookup_token(data,0,n)} else {MISS};
                    assert_eq!(actual,vec![id;17],"length {n}, offset {offset}");
                }
            }
            assert_eq!(munmap(map,page*3),0);
        }
    }
}
