#[cfg(all(test, any(all(target_arch="x86_64",target_feature="sse4.2"),b_medium_crc_emulate)))]
mod medium_properties {
 use super::*;
 #[cfg(not(b_medium_crc_forced))]
 fn reference(a:u64,b:u64)->usize {
  let mut c=0u32;
  for word in [a,b] { for byte in word.to_le_bytes() {c^=byte as u32;for _ in 0..8 {c=(c>>1)^(0x82f63b78 & 0u32.wrapping_sub(c&1));}}}
  c as usize
 }
 #[cfg(not(b_medium_crc_forced))]
 #[test] fn crc_and_lengths() {
  let mut x=0x9e3779b97f4a7c15u64;
  for _ in 0..300000 {x^=x<<13;x^=x>>7;x^=x<<17;let a=x;x^=x<<13;x^=x>>7;x^=x<<17;assert_eq!(medium_crc(a,x),reference(a,x));}
  let mut p=Plan{slots:vec![MISS;64],..Default::default()};
  let words:[&[u8];6]=[b"abcdefgh",b"abcdefghi",b"abcdefghijklmnop",b"abcdefghijklmnopq",b"000000000",b"9999999999999999"];
  let ids:Vec<_>=words.iter().map(|w|p.intern(w,IN_BOOL)).collect();
  p.build_short();p.build_medium();assert!(p.medium_mode);
  for (word,id) in words.iter().zip(ids) {assert_eq!(p.lookup_token(word,0,word.len()),id);let u=word.to_ascii_uppercase();assert_eq!(p.lookup_token(&u,0,u.len()),id);}
  for word in [b"abcdefgzz".as_slice(),b"abcdefghijklmnox".as_slice(),b"abcdefghijklmnoqq".as_slice()] {assert_eq!(p.lookup_token(word,0,word.len()),MISS);}
  let mut p=Plan{slots:vec![MISS],..Default::default()};p.build_short();p.build_medium();assert!(p.medium_mode);
  for w in [b"abcdefghi".as_slice(),b"abcdefghijklmnop".as_slice(),b"abcdefghijklmnopq".as_slice()] {assert_eq!(p.lookup_token(w,0,w.len()),MISS);}
 }
 #[cfg(not(b_medium_crc_forced))]
 #[test] fn fallback_thresholds() {
  let mut buckets:Vec<Vec<Vec<u8>>>=vec![Vec::new();256];
  for i in 0..1_000_000u32 {let w=format!("m{i:08x}").into_bytes();let k=key(&w,0,w.len());let bucket=medium_crc(k.0[0],k.0[1])&255;
   if buckets[bucket].len()<36 {buckets[bucket].push(w);}
   if buckets[1].len()>=34 && (200..256).chain(0..=8).all(|b|!buckets[b].is_empty()) && !buckets[50].is_empty() {break;}
  }
  assert!(buckets[1].len()>=34);
  for (n,accept) in [(33,true),(34,false)] {
   let mut p=Plan{slots:vec![MISS;1024],..Default::default()};
   // 65 total keys guarantees 256 slots; add 32 distinct nonadjacent-home fillers.
   let mut v=buckets[1][..n].to_vec();
   for (i,slot) in buckets.iter().enumerate() { if i != 1 && !slot.is_empty() && v.len()<65 {v.push(slot[0].clone());} }
   assert_eq!(v.len(),65);
   let ids:Vec<_>=v.iter().map(|w|p.intern(w,IN_BOOL)).collect();p.build_short();p.build_medium();
   if !accept {assert!(!p.medium_mode,"33 displaced entries must reject trial");}
   // For the 33-key case, filler buckets can collide with the run, so only prove lookups.
   for (w,id) in v.iter().zip(ids) {assert_eq!(p.lookup_token(w,0,w.len()),id);}
  }
  for (extra,accept) in [(false,true),(true,false)] {
   let mut p=Plan{slots:vec![MISS;1024],..Default::default()};let mut v=Vec::new();
   for i in (200..256).chain(0..=if extra {8} else {7}) {assert!(!buckets[i].is_empty());v.push(buckets[i][0].clone());}
   v.push(buckets[50][0].clone());let ids:Vec<_>=v.iter().map(|w|p.intern(w,IN_BOOL)).collect();
   p.build_short();p.build_medium();assert_eq!(p.medium_mode,accept,"wrap-run threshold");
   for (w,id) in v.iter().zip(ids) {assert_eq!(p.lookup_token(w,0,w.len()),id);}
  }
 }
 #[cfg(b_medium_crc_forced)]
 #[test] fn forced_fallback() {
  let mut p=Plan{slots:vec![MISS;1024],..Default::default()};let mut words=Vec::new();
  for i in 0..100u32 {let w=format!("m{i:08x}").into_bytes();let id=p.intern(&w,IN_BOOL);words.push((w,id));}
  p.build_short();p.build_medium();assert!(!p.medium_mode);assert!(p.medium_slots.is_empty());
  for (w,id) in words {assert_eq!(p.lookup_token(&w,0,w.len()),id);}
 }
}
#[cfg(all(test,target_os="linux",target_arch="x86_64",target_feature="sse4.2"))]
mod medium_guard {
 use super::*;
 use std::ffi::c_void;
 extern "C" {fn mprotect(p:*mut c_void,n:usize,prot:i32)->i32;fn munmap(p:*mut c_void,n:usize)->i32;fn sysconf(n:i32)->isize;}
 #[test] fn protected_page_boundaries() {
  assert!(std::arch::is_x86_feature_detected!("sse4.2"));
  let page=unsafe{sysconf(30)} as usize;assert!(page>=4096&&page.is_power_of_two());
  let ptr=unsafe{mmap(std::ptr::null_mut(),page*3,3,0x22,-1,0)} as *mut u8;assert_ne!(ptr as isize,-1);
  unsafe {
   assert_eq!(mprotect(ptr.cast(),page,0),0);assert_eq!(mprotect(ptr.add(page*2).cast(),page,0),0);
   let mut p=Plan{slots:vec![MISS;128],..Default::default()};let mut words=Vec::new();
   for n in 8..=17 {let w=vec![b'a';n];let id=p.intern(&w,IN_BOOL);words.push((w,id));}
   p.build_short();p.build_medium();assert!(p.medium_mode);
   for (w,id) in words {for dst in [ptr.add(page),ptr.add(page*2-w.len())] {
    std::ptr::copy_nonoverlapping(w.as_ptr(),dst,w.len());assert_eq!(p.lookup_token(std::slice::from_raw_parts(dst,w.len()),0,w.len()),id);
   }}
   assert_eq!(munmap(ptr.cast(),page*3),0);
  }
 }
}
