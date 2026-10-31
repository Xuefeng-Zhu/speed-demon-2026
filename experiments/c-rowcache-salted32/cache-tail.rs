#[cfg(test)] mod cache_review {
 use super::*;
 use std::collections::HashSet;
 fn leaked(s:&str)-> &'static [u8] { Box::leak(s.as_bytes().to_vec().into_boxed_slice()) }
 #[test]
 fn distinct_hashes_same_cache_slot() {
  let mut d=OwnerDict::default(); let mut entries=Vec::new();
  for i in 0..8_000usize {
   let name=leaked(&format!("name-{i:05}")); let h=(i as u64)*CACHE_SLOTS as u64;
   let g=[0usize,63,64,127,128,511,512][i%7];
   assert_eq!(d.see(name,h,g,9),1);entries.push((name,h,g));
  }
  for &(name,h,g) in entries.iter().rev() {
   assert_eq!(d.see(name,h,g,9),0);
   assert_eq!(d.see(name,h,(g+1)%513,9),1);
   assert_eq!(d.see(name,h,(g+1)%513,9),0);
  }
 }
 #[test]
 fn full_hash_collision_promotion_and_reallocation() {
  let mut d=OwnerDict::default(); let mut entries=Vec::new();
  for i in 0..50_000usize {
   let name=leaked(&format!("item-{i:06}"));
   assert_eq!(d.see(name,0,256,9),1); entries.push(name);
  }
  assert_eq!(d.heads[&0],PROMOTED); assert_eq!(d.entries.len(),50_000);
  for name in entries.iter().rev() {
   assert_eq!(d.see(name,0,256,9),0);assert_eq!(d.see(name,0,512,9),1);
  }
 }
 #[test]
 fn random_mixed_hashes_match_model() {
  let mut d=OwnerDict::default(); let mut seen=HashSet::<(Vec<u8>,u64,usize)>::new();let mut x=0x6a09e667f3bcc909u64;
  for _ in 0..100_000 {
   x^=x<<13;x^=x>>7;x^=x<<17;let idx=(x%997) as usize;
   let name=leaked(&format!("n-{idx:04}"));
   let h=if idx%3==0 {0} else {((idx%401)*CACHE_SLOTS) as u64}; let group=((x>>20)%513) as usize;
   let expected=seen.insert((name.to_vec(),h,group)) as i64;
   assert_eq!(d.see(name,h,group,9),expected);
  }
 }
}
