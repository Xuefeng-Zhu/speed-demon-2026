#[cfg(test)]
mod packed_threshold {
 use super::*;
 #[test]
 fn sentinel_and_threshold_boundaries() {
  let mut word=Vec::new();
  for n in 0..1_000_000u32 {
   let s=format!("{n:08x}"); let x=u64::from_le_bytes(s.as_bytes().try_into().unwrap());
   if Plan::short_hash(x) as u32 & 0xfff8_0000 == 0xfff8_0000 { word=s.into_bytes();break; }
  }
  let need_all_ones= !cfg!(forced_hash_test);
  if need_all_ones { assert!(!word.is_empty()); }
  if word.is_empty() {word=b"12345678".to_vec();}
  for &(n,tagged) in &[(0usize,true),(1,true),(0x7fffe,true),(0x7ffff,true),(0x80000,false)] {
   let mut p=Plan::default();
   p.keys=vec![Key([0,1,0,0]);n];
   if n!=0 { p.keys[n-1]=key(&word,0,word.len()); }
   p.build_short();
   assert_eq!(p.short_tagged,tagged,"n={n}");
   let got=p.lookup_token(&word,0,word.len());
   assert_eq!(got,if n==0 { MISS } else { (n-1) as u32 },"n={n}");
   assert_eq!(p.lookup_token(b"notword",0,7),MISS);
   if n>0 { assert!(p.short_slots.iter().any(|&v|v!=MISS)); }
  }
 }
}
