#!/usr/bin/env python3
from pathlib import Path
import subprocess,tempfile
src=Path(__file__).with_name('candidate.rs').read_text()
tail=r'''
#[cfg(test)] mod model {
use super::*; use std::collections::BTreeMap;
#[test] fn near_far_transition_reversal() {
 let mut h=FastHeap::new();
 for &(q,offset,v) in &[(260u64,10u64,1u32),(511,2,2),(1000,0,3)] {assert!(h.push((q<<BUCKET_SHIFT)+offset,v));}
 assert_eq!(h.top(),Some(260<<BUCKET_SHIFT)); assert!(h.far_last<=511);
 assert_eq!(h.pop().1,1);
 // During the active window, both an earlier in-window insertion and a
 // just-outside-window insertion are legal despite far_last reaching 511.
 assert!(h.push((261<<BUCKET_SHIFT)+3,4));assert!(h.push((512<<BUCKET_SHIFT)+5,5));
 for &(q,v) in &[(261,4),(511,2),(512,5),(1000,3)] {
  assert_eq!(h.top(),Some(q<<BUCKET_SHIFT));assert_eq!(h.pop().1,v);
 }
 assert_eq!(h.top(),None);
 h.clear();
 let high=(u32::MAX as u64-1)>>BUCKET_SHIFT;
 for &(q,v) in &[(0,7),(255,8),(256,9),(high,10)] {assert!(h.push(q<<BUCKET_SHIFT,v));}
 for &(q,v) in &[(0,7),(255,8),(256,9),(high,10)] {assert_eq!(h.top(),Some(q<<BUCKET_SHIFT));assert_eq!(h.pop().1,v);}
 assert_eq!(h.top(),None);
}
#[test] fn coarse_window_multiset() {
 let mut h=FastHeap::new();let mut r=BTreeMap::<u64,Vec<(u64,u32)>>::new();let mut last=0u64;let mut z=0x49abcde087654321u64;
 for step in 0..1_000_000u32 {
  z ^= z<<13;z ^= z>>7;z ^= z<<17;
  if step%1379==0 {h.clear();r.clear();last=0;}
  if r.is_empty() || z%10<6 {
   let delta=match z%17 {0=>0,1=>255,2=>256,3=>257,4=>65535,5=>1_000_000,_=>(z>>9)%1000};
   let q=(last+delta).min((u32::MAX as u64-1)>>BUCKET_SHIFT);let key=(q<<BUCKET_SHIFT)|((z>>20)&63);
   assert!(h.push(key,step));r.entry(q).or_default().push((key,step));
  } else {
   let q=*r.first_key_value().unwrap().0;assert_eq!(h.top().unwrap(),q<<BUCKET_SHIFT);last=q;
   let (key,v)=h.pop();assert_eq!(key>>BUCKET_SHIFT,q);let list=r.get_mut(&q).unwrap();let i=list.iter().position(|&e|e==(key,v)).unwrap();list.swap_remove(i);if list.is_empty(){r.remove(&q);}
  }
  assert_eq!(h.count,r.values().map(Vec::len).sum());
 }
 while !r.is_empty(){let q=*r.first_key_value().unwrap().0;assert_eq!(h.top().unwrap(),q<<BUCKET_SHIFT);let(key,v)=h.pop();let list=r.get_mut(&q).unwrap();let i=list.iter().position(|&e|e==(key,v)).unwrap();list.swap_remove(i);if list.is_empty(){r.remove(&q);}}
 assert_eq!(h.top(),None);
}
}
'''
with tempfile.TemporaryDirectory(prefix='d-coarse-window-model-') as tmp:
 p=Path(tmp);s=p/'model.rs';b=p/'model';s.write_text(src+tail)
 subprocess.run(['rustc','--edition=2021','-O','-C','overflow-checks=yes','-C','debug-assertions=yes','--test',str(s),'-o',str(b)],check=True)
 subprocess.run([str(b),'--test-threads=1'],check=True)
