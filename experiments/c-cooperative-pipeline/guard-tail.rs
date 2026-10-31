use std::ffi::c_void;
unsafe extern "C" { fn mprotect(a:*mut c_void,n:usize,prot:i32)->i32; fn munmap(a:*mut c_void,n:usize)->i32; fn getpagesize()->i32; }
#[test]
fn page_boundary_field_scan() { unsafe {
 let pg=getpagesize() as usize;
 #[cfg(target_os="macos")] let anon=0x1000;
 #[cfg(not(target_os="macos"))] let anon=0x20;
 let m=mmap(std::ptr::null_mut(),2*pg,3,2|anon,-1,0) as *mut u8;
 assert_ne!(m as isize,-1); assert_eq!(mprotect(m.add(pg).cast(),pg,0),0);
 for len in 0..=1024.min(pg-3) { for escaped in [false,true] {
  if escaped && len<2 {continue;}
  let size=len+3;let ptr=m.add(pg-size);*ptr=b'"'; std::ptr::write_bytes(ptr.add(1),b'a',len);
  if escaped {*ptr.add(1+len/2-1)=b'"';*ptr.add(1+len/2)=b'"';}
  *ptr.add(1+len)=b'"';*ptr.add(2+len)=b',';
  let data:&'static[u8]=std::slice::from_raw_parts(ptr,size);
  let (mut p,mut q)=(0usize,0usize);let (name,n)=field(data,&mut p);let (got,nn,h)=field_name_hash(data,&mut q);
  assert_eq!((got,nn,q),(name,n,p));assert_eq!(h,name_hash(name));
 }}
 // Explicit split pairs and closing quotes immediately before a protected page.
 for len in [9usize, 10, 17, 33, 34, 65, 66, 127, 128] {
  for pos in [0usize, 6, 7, 8, 30, 31, 32, len-2] {
   if pos+1>=len {continue;}
   let size=len+3; let ptr=m.add(pg-size); *ptr=b'"'; std::ptr::write_bytes(ptr.add(1),b'a',len);
   *ptr.add(1+pos)=b'"'; *ptr.add(2+pos)=b'"'; *ptr.add(1+len)=b'"'; *ptr.add(2+len)=b',';
   let data:&'static[u8]=std::slice::from_raw_parts(ptr,size);
   let (mut p,mut q)=(0usize,0usize); let (name,n)=field(data,&mut p); let (got,nn,h)=field_name_hash(data,&mut q);
   assert_eq!((got,nn,q),(name,n,p)); assert_eq!(h,name_hash(name));
  }
 }
 assert_eq!(munmap(m.cast(),pg*2),0);
}}
