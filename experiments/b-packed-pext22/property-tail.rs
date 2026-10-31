#[cfg(test)]
mod exact_packed_tests {
 use super::*;
 fn new_plan(cap:usize)->Plan<'static> { let mut p=Plan::default();p.slots=vec![MISS;cap.next_power_of_two()];p }
 #[test] fn exhaustive_three_and_case() {
  let alphabet=b"abcdefghijklmnopqrstuvwxyz0123456789";let mut p=new_plan(1<<18);let mut ws=Vec::new();
  for &a in alphabet { ws.push(vec![a]);for &b in alphabet {ws.push(vec![a,b]);for &c in alphabet {ws.push(vec![a,b,c]);}}}
  for w in &ws {p.intern(w,0);} p.build_short();assert!(!p.packed_short.is_empty());
  for (id,w) in ws.iter().enumerate() { assert_eq!(p.lookup_token(w,0,w.len()),id as u32);let u:Vec<_>=w.iter().map(u8::to_ascii_uppercase).collect();assert_eq!(p.lookup_token(&u,0,u.len()),id as u32); }
  assert_eq!(p.lookup_token(b"",0,0),MISS);
 }
 #[test] fn shared_seven_prefix_and_misses() {
   let mut p=new_plan(256);let abc=b"abcdefghijklmnopqrstuvwxyz0123456789";let mut ws=Vec::new();
   for &c in abc {let mut w=b"abcdefg".to_vec();w.push(c);ws.push(w);} ws.push(b"abcdefg".to_vec());ws.push(b"abcdef".to_vec());
   for w in &ws {p.intern(w,0);}p.build_short();assert!(!p.packed_short.is_empty());
   for (id,w) in ws.iter().enumerate(){assert_eq!(p.lookup_token(w,0,w.len()),id as u32);}
   assert_eq!(p.lookup_token(b"abcdeffz",0,8),MISS);
   let mut incomplete=new_plan(256);
   for w in &ws[..35] { incomplete.intern(w,0); }
   incomplete.build_short();
   assert_eq!(incomplete.lookup_token(b"abcdefg9",0,8),MISS);
 }
 #[test] fn id_width_boundary() {
  let lim=1usize<<21;
  for size in [lim, lim+1] {
   let mut p=new_plan(2);p.keys=vec![Key([0,1,0,0]);size];p.keys[size-1]=key(b"abc",0,3);p.build_short();
   assert_eq!(!p.packed_short.is_empty(),size==lim);assert_eq!(p.lookup_token(b"abc",0,3), (size-1) as u32);assert_eq!(p.lookup_token(b"abd",0,3),MISS);
  }
 }
 #[cfg(target_os="linux")]
 #[test] fn guarded_page_lookups() {
   unsafe extern "C" { fn mprotect(p:*mut u8,n:usize,prot:i32)->i32; fn munmap(p:*mut u8,n:usize)->i32; }
   let mut p=new_plan(128);let words=["a","a1","abc","word","Words","abc123","abcdefg","abcdefg1","abcdefg2"];
   for w in words {p.intern(w.as_bytes(),0);}p.build_short();
   unsafe {
     let base=mmap(std::ptr::null_mut(),12288,0,0x22,-1,0);assert_ne!(base as isize,-1);assert!(!base.is_null());
     assert_eq!(mprotect(base.add(4096),4096,3),0);
     for (id,w) in words.iter().enumerate() {let n=w.len(); for off in [4096,8192-n] {
       let dst=base.add(off);std::ptr::copy_nonoverlapping(w.as_ptr(),dst,n);
       let s=std::slice::from_raw_parts(dst,n);assert_eq!(p.lookup_token(s,0,n),id as u32);
     }}
     assert_eq!(munmap(base,12288),0);
   }
 }

}
