#[cfg(test)] mod pool_property {
 use super::*; use std::collections::BTreeMap;
 #[test] fn randomized_pool_matches_multiset() {
  let mut h=FastHeap::new(); let mut m=BTreeMap::<(u64,u32),usize>::new(); let mut seed=0x42aabbeeff334477u64;
  for i in 0..1_000_000 {
   seed^=seed<<13; seed^=seed>>7; seed^=seed<<17;
   if i%7501==0 {h.clear();m.clear();}
   let total:usize=m.values().sum();
   if !m.is_empty() && (seed%3!=0 || total>512) {
    let min=h.top().unwrap();let expected=m.first_key_value().unwrap().0.0;assert_eq!(min,expected);
    let (d,v)=h.pop();let c=m.get_mut(&(d,v)).unwrap();*c-=1;if *c==0 {m.remove(&(d,v));}
   } else {
    let k=h.last+((seed>>24)&0xffff);let v=(seed>>32) as u32%257;
    assert!(h.push(k,v));*m.entry((k,v)).or_default()+=1;
   }
   assert_eq!(h.count,m.values().sum());
   if i%101==0 {assert_eq!(h.top(),m.first_key_value().map(|(k,_)|k.0));}
  }
 }
}
