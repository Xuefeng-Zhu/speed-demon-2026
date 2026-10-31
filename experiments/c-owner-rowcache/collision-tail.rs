#[cfg(test)] mod review_bucket {
 use super::*;
 use std::collections::HashSet;
 fn leaked(v:&str)-> &'static [u8] { Box::leak(v.as_bytes().to_vec().into_boxed_slice()) }
 #[test]
 fn thresholds_and_interleaved_hashes() {
  for words in [1,2,4,9] {
   let mut d=OwnerDict::default();let mut seen=HashSet::<(Vec<u8>,usize)>::new();
   let names:Vec<String>=(0..300).map(|i|format!("name-{i:04}")).collect();
   for pass in 0..4 { for j in 0..names.len() {
    let i=(j*137+pass*91)%names.len();let h=(i%3) as u64;let group=(i*19+pass*31)%(words*64);
    let n=leaked(&names[i]);let expected=seen.insert((n.to_vec(),group)) as i64;
    assert_eq!(d.see(n,h,group,words),expected,"pass={pass} i={i} words={words}");
   }}
   assert_eq!(d.entries.len(),300);assert_eq!(d.bits.len(),300*words);
   for h in 0..3u64 {assert_eq!(d.heads[&h],PROMOTED);assert_eq!(d.promoted[&h].len(),100);}
  }
 }
 #[test]
 fn exact_promotion_boundary() {
  let mut d=OwnerDict::default();
  for n in 0..8 { let name=leaked(&format!("n{n}")); assert_eq!(d.see(name,0,0,1),1); }
  assert_ne!(d.heads[&0],PROMOTED);assert!(d.promoted.is_empty());
  for n in 0..8 { assert_eq!(d.see(leaked(&format!("n{n}")),0,0,1),0); }
  assert_ne!(d.heads[&0],PROMOTED);
  assert_eq!(d.see(leaked("n8"),0,0,1),1);assert_eq!(d.heads[&0],PROMOTED);
  for n in 0..9 { let name=leaked(&format!("n{n}"));assert_eq!(d.see(name,0,0,1),0);assert_eq!(d.see(name,0,63,1),1);assert_eq!(d.see(name,0,63,1),0); }
 }
 #[test]
 fn large_forced_collision_family() {
  let mut d=OwnerDict::default();let count=50_000usize;
  for n in 0..count { let name=leaked(&format!("item-{n:06}"));assert_eq!(d.see(name,0,256,9),1); }
  assert_eq!(d.heads[&0],PROMOTED);assert_eq!(d.promoted[&0].len(),count);assert_eq!(d.entries.len(),count);assert_eq!(d.bits.len(),count*9);
  for n in (0..count).rev() {let name=leaked(&format!("item-{n:06}"));assert_eq!(d.see(name,0,256,9),0);assert_eq!(d.see(name,0,512,9),1);}
 }
 #[test]
 fn empty_and_distinct_byte_patterns() {
  let mut d=OwnerDict::default();let names=["", "A", "A ", "A  ", "A,B", "A\"\"B", " ", "x", "xx", "X"];
  for (i,name) in names.iter().enumerate() {
   assert_eq!(d.see(leaked(name),u64::MAX,256,9),1,"{i}");
  }
  assert_eq!(d.heads[&u64::MAX],PROMOTED);
  for name in names {assert_eq!(d.see(leaked(name),u64::MAX,256,9),0);assert_eq!(d.see(leaked(name),u64::MAX,255,9),1);}
 }

}
#[cfg(test)] mod clustered_hash_review {
 use super::*;
 use std::time::Instant;
 #[test]
 fn salted_owner_handles_clustered_distinct_hashes_exactly() {
  const N:usize=16_384;
  let mut d=OwnerDict::default();let mut rows=Vec::new();
  let start=Instant::now();
  for i in 0..N {
   // Artificial prehashes reproduce the prior low-bucket/control-bit pattern.
   // No claim is made that these are attainable from legal Fx name inputs.
   let rotated=((i as u64&255)<<20)|((i as u64>>8)<<32);
   let h=rotated.rotate_right(32);
   assert_eq!(((h as u128*12)>>64),0);
   let name:&'static [u8]=Box::leak(format!("name-{i:06}").into_bytes().into_boxed_slice());
   assert_eq!(d.see(name,h,0,1),1);rows.push((name,h));
  }
  let elapsed=start.elapsed();
  for (name,h) in rows { assert_eq!(d.see(name,h,0,1),0);assert_eq!(d.see(name,h,63,1),1); }
  println!("salted distinct prehashes {N}, first-insert {:.3} ms; legal Fx preimages not established",elapsed.as_secs_f64()*1000.);
 }
}
