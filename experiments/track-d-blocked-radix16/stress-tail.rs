#[cfg(test)] mod blocked_property {
 use super::*; use std::collections::{BTreeMap,HashSet};
 fn audit(h:&FastHeap) {
  let mut seen=HashSet::new(); let mut count=0;
  for bucket in 0..33 {let mut id=h.head[bucket];let mut first=true;while id!=END {
   assert!((id as usize)<h.fresh);assert!(seen.insert(id));let b=&h.blocks[id as usize];
   assert!(b.len>0 && b.len<=BLOCK_LEN);if !first {assert_eq!(b.len,BLOCK_LEN)}
   for x in &b.items[..b.len] {assert_eq!(h.slot(x>>32),bucket)} count+=b.len;first=false;id=b.next;
  }}
  let mut id=h.free;while id!=END {assert!((id as usize)<h.fresh);assert!(seen.insert(id));id=h.blocks[id as usize].next;}
  assert_eq!(seen.len(),h.fresh);assert_eq!(count,h.count);assert!(h.fresh<=BLOCK_COUNT);
 }
 #[test] fn fragmentation_and_refill() {
  let mut h=FastHeap::new();let mut map=BTreeMap::<(u64,u32),usize>::new();
  for i in 0..POOL_CAP {let k=if i%7==0 {u32::MAX as u64-1} else {1u64<<(i%31)};let v=(i%13) as u32;
   assert!(h.push(k,v));*map.entry((k,v)).or_default()+=1;}
  audit(&h);assert!(!h.push(0,0));
  for i in 0..POOL_CAP*3 {
   let min=*map.first_key_value().unwrap().0;assert_eq!(h.top(),Some(min.0));let p=h.pop();
   let c=map.get_mut(&p).unwrap();*c-=1;if *c==0 {map.remove(&p);}
   let k=if i%3==0 {h.last} else if i%3==1 {u32::MAX as u64-1} else {(h.last + (i as u64 & 2047)).min(u32::MAX as u64-1)};
   let v=(i%13) as u32;assert!(h.push(k,v));*map.entry((k,v)).or_default()+=1;
   if i%997==0 {audit(&h)}
  }
  while let Some((&(k,_),_))=map.first_key_value() {assert_eq!(h.top(),Some(k));let p=h.pop();let c=map.get_mut(&p).unwrap();*c-=1;if *c==0 {map.remove(&p);}}
  assert_eq!(h.top(),None);audit(&h);
  for _ in 0..10 {h.clear();assert_eq!(h.top(),None);audit(&h);}
 }
}
