use std::ffi::c_void;
unsafe extern "C" { fn mprotect(a:*mut c_void,n:usize,prot:i32)->i32; fn munmap(a:*mut c_void,n:usize)->i32; fn getpagesize()->i32; }
#[test]
fn structural_page_boundaries_and_split_quotes() { unsafe {
 let pg=getpagesize() as usize;
 #[cfg(target_os="macos")] let anon=0x1000;
 #[cfg(not(target_os="macos"))] let anon=0x20;
 let m=mmap(std::ptr::null_mut(),3*pg,3,2|anon,-1,0) as *mut u8;
 assert_ne!(m as isize,-1);assert_eq!(mprotect(m.cast(),pg,0),0);assert_eq!(mprotect(m.add(2*pg).cast(),pg,0),0);
 for len in 0..=1024.min(pg-3) {for at_end in [false,true] {for escaped in [false,true] {
  if escaped && len<2 {continue;} let size=len+3;
  let ptr=if at_end {m.add(2*pg-size)} else {m.add(pg)};
  *ptr=b'"';std::ptr::write_bytes(ptr.add(1),b'a',len);
  if escaped {*ptr.add(1+len/2-1)=b'"';*ptr.add(1+len/2)=b'"';}
  *ptr.add(1+len)=b'"';*ptr.add(2+len)=b',';
  let data:&'static [u8]=std::slice::from_raw_parts(ptr,size);let mut c=StructuralCursor::new(data,0,size);
  let (s,e,q)=c.span();let (got,gn)=structural_text(data,s,e,q);let mut p=0;let (expected,en)=field(data,&mut p);
  assert_eq!((got,gn,e+1),(expected,en,p));
 }}}
 for len in [34usize,65,66,97,129] {for pos in [0usize,30,31,32,len-2] { if pos+1>=len {continue;}
  let size=len+3;let ptr=m.add(2*pg-size);*ptr=b'"';std::ptr::write_bytes(ptr.add(1),b'a',len);
  *ptr.add(1+pos)=b'"';*ptr.add(2+pos)=b'"';*ptr.add(1+len)=b'"';*ptr.add(2+len)=b',';
  let data:&'static[u8]=std::slice::from_raw_parts(ptr,size);let mut c=StructuralCursor::new(data,0,size);
  let (s,e,q)=c.span();let(got,gn)=structural_text(data,s,e,q);let mut p=0;let(expected,en)=field(data,&mut p);
  assert_eq!((got,gn,e+1),(expected,en,p));
 }}
 assert_eq!(munmap(m.cast(),3*pg),0);
}}
