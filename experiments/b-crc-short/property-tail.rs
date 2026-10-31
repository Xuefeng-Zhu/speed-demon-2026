#[cfg(all(test, any(all(target_arch="x86_64", target_feature="sse4.2"), b_crc_emulate)))]
mod crc_properties {
 use super::*;
 fn crc_reference(x:u64)->usize {
  let mut c=0u32;
  for b in x.to_le_bytes() {c^=b as u32;for _ in 0..8 {c=(c>>1)^(0x82f63b78 & (0u32.wrapping_sub(c&1)));}}
  c as usize
 }
 #[cfg(not(b_crc_forced_collision))]
 #[test] fn exact_crc_and_normal_mode(){
  let mut x=0x6a09e667f3bcc909u64;
  for _ in 0..300000 {x^=x<<13;x^=x>>7;x^=x<<17;assert_eq!(short_crc(x),crc_reference(x));}
  let mut p=Plan{slots:vec![MISS;16],..Default::default()};
  let a=p.intern(b"abc",IN_BOOL);p.build_short();assert!(p.short_crc_mode);
  assert_eq!(p.lookup_token(b"ABC",0,3),a);assert_eq!(p.lookup_token(b"bad",0,3),MISS);
  let mut p=Plan{slots:vec![MISS],..Default::default()};p.build_short();assert!(p.short_crc_mode);assert_eq!(p.lookup_token(b"a",0,1),MISS);
 }
 #[cfg(not(b_crc_forced_collision))]
 #[test] fn cyclic_cluster_guard(){
  // 65 different home buckets wrap over the end of the 256-slot table.
  // No key is displaced at insertion, but an absent lookup must not scan
  // this cluster when CRC mode is selected.
  let mut buckets:Vec<Option<Vec<u8>>>=vec![None;256]; let mut n=0;
  for i in 0..1_000_000 {let word=format!("{i:07x}").into_bytes();let k=key(&word,0,word.len()).0[0];let bucket=short_crc(k)&255;
   if (bucket>=200 || bucket<=8) && buckets[bucket].is_none(){buckets[bucket]=Some(word);n+=1;if n==65 {break}}
  }
  assert_eq!(n,65);let mut p=Plan{slots:vec![MISS;512],..Default::default()};let mut pairs=Vec::new();
  for word in buckets.into_iter().flatten(){let id=p.intern(&word,IN_BOOL);pairs.push((word,id));}
  p.build_short();assert!(!p.short_crc_mode,"65-slot cyclic run must disable CRC");
  for (word,id) in pairs {assert_eq!(p.lookup_token(&word,0,word.len()),id);}
 }
 #[cfg(b_crc_forced_collision)]
 #[test] fn insertion_guard_fallback(){
  let mut p=Plan{slots:vec![MISS;512],..Default::default()};let mut pairs=Vec::new();
  for i in 0..100 {let word=format!("{i:07x}").into_bytes();let id=p.intern(&word,IN_BOOL);pairs.push((word,id));}
  p.build_short();assert!(!p.short_crc_mode,"33 displaced keys must disable CRC");
  for (word,id) in pairs{assert_eq!(p.lookup_token(&word,0,word.len()),id);}
 }
}
#[cfg(all(test, target_os="linux", target_arch="x86_64", target_feature="sse4.2"))]
mod crc_guard_pages {
 use super::*;
 use std::ffi::c_void;
 extern "C" {
  fn mprotect(addr:*mut c_void,len:usize,prot:i32)->i32;
  fn munmap(addr:*mut c_void,len:usize)->i32;
  fn sysconf(name:i32)->isize;
 }
 #[test]
 fn short_lookup_at_guard_pages() {
  assert!(std::arch::is_x86_feature_detected!("sse4.2"));
  let page=unsafe{sysconf(30)} as usize; assert!(page>=4096 && page.is_power_of_two());
  let ptr=unsafe{mmap(std::ptr::null_mut(),page*3,3,0x22,-1,0)} as *mut u8; assert_ne!(ptr as isize,-1);
  unsafe {
   assert_eq!(mprotect(ptr.cast(),page,0),0);assert_eq!(mprotect(ptr.add(page*2).cast(),page,0),0);
   let mut p=Plan{slots:vec![MISS;64],..Default::default()};
   let mut terms=Vec::new();
   for n in 1..=9 {let w=vec![b'a';n];let id=p.intern(&w,IN_BOOL);terms.push((w,id));}
   p.build_short();assert!(p.short_crc_mode);
   for (w,id) in terms {
    for dst in [ptr.add(page),ptr.add(page*2-w.len())] {
     std::ptr::copy_nonoverlapping(w.as_ptr(),dst,w.len());
     assert_eq!(p.lookup_token(std::slice::from_raw_parts(dst,w.len()),0,w.len()),id);
    }
   }
   assert_eq!(munmap(ptr.cast(),page*3),0);
  }
 }
}
