
#[cfg(test)]
mod independent {
 use super::*;
 #[test]
 fn randomized_headmap_matches_std() {
  let mut a=HeadMap::default(); let mut b=HashMap::<u64,usize>::new();let mut x=0x6a09e667f3bcc909u64;
  for i in 0..400_000usize {
   x^=x<<13;x^=x>>7;x^=x<<17;
   let k=if i%7==0 {x%1500} else {x}; let v=if i%47==0 {PROMOTED} else {i};
   a.insert(k,v);b.insert(k,v);
   if i%31==0 {assert_eq!(a.get(&k),b.get(&k).copied());}
  }
  for (k,v) in b {assert_eq!(a.get(&k),Some(v));}
 }
 #[test]
 fn forced_probe_cap_preserves_zero_and_promoted_values() {
  let mut m=HeadMap::default();m.salt=0;m.slots=vec![(0,NONE);256];m.used=0;
  let keys:Vec<u64>=(0..).filter(|&k|HeadMap::index(k,0,255)==0).take(33).collect();
  for (i,&k) in keys.iter().enumerate(){m.insert(k,if i==0 {PROMOTED}else{i});if i<32 {assert!(m.fallback.is_none());}}
  assert!(m.fallback.is_some());
  for (i,&k) in keys.iter().enumerate(){assert_eq!(m.get(&k),Some(if i==0 {PROMOTED}else{i}));}
  m.insert(keys[2],PROMOTED);assert_eq!(m.get(&keys[2]),Some(PROMOTED));
  m.insert(0,123);assert_eq!(m.get(&0),Some(123));
 }
 #[test]
 fn outer_cap_and_inner_chain_promotion_interact_exactly() {
  let mut d=OwnerDict::default();d.heads.salt=0;d.heads.slots=vec![(0,NONE);256];d.heads.used=0;
  let hashes:Vec<u64>=(0..).filter(|&k|HeadMap::index(k,0,255)==0).take(33).collect();
  let mut names=Vec::new();
  for (i,&h) in hashes.iter().enumerate(){
   for j in 0..10 {
    let n:&'static[u8]=Box::leak(format!("/family-{i:02}-{j:02}").into_bytes().into_boxed_slice());
    let g=[0,63,64,127,128,511,512][(i+j)%7];
    assert_eq!(d.see(n,h,g,9),1); names.push((n,h,g));
   }
  }
  assert!(d.heads.fallback.is_some());
  for &(n,h,g) in &names {assert_eq!(d.see(n,h,g,9),0);assert_eq!(d.see(n,h,(g+1)%513,9),1);}
  for &(n,h,g) in &names {assert_eq!(d.see(n,h,(g+1)%513,9),0);}
 }
 #[test]
 fn fifty_thousand_equal_hash_distinct_names() {
  let mut d=OwnerDict::default();let mut names=Vec::new();
  for i in 0..50_000 {let n:&'static[u8]=Box::leak(format!("person-{i}").into_bytes().into_boxed_slice()); assert_eq!(d.see(n,0,0,1),1); names.push(n);}
  for n in names {assert_eq!(d.see(n,0,0,1),0);}
 }
}
