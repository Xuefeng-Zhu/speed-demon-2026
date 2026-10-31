#[cfg(test)]
mod direct_review {
 use super::*;use std::sync::{Barrier,atomic::AtomicPtr};
 #[test]
 fn concurrent_claim_collision_and_bits() {
  for workers in [1usize,2,8,32] {for _ in 0..3 {
   let values:Vec<Vec<u8>>=(0..64).map(|i|format!("name {i}").into_bytes()).chain([vec![],b"Ann \"\"Annie\"\"".to_vec(),b"A ".to_vec()]).collect();
   let a:Vec<&'static[u8]>=values.iter().map(|x| &*Box::leak(x.clone().into_boxed_slice())).collect();
   let b:Vec<&'static[u8]>=values.iter().map(|x| &*Box::leak(x.clone().into_boxed_slice())).collect();
   let groups=[0usize,1,63,64,65,127,128,191,192,239,254,255];
   let slots:Vec<AtomicPtr<DirectNode>>=vec![AtomicPtr::new(std::ptr::null_mut())];
   let shards:Vec<DirectShard>=(0..1024).map(|_|DirectShard::default()).collect();let barrier=Barrier::new(workers);
   let sum:i64=thread::scope(|scope|{
    let mut hs=Vec::new();for t in 0..workers {let (a,b,slots,shards,groups,barrier)=(&a,&b,&slots,&shards,&groups,&barrier);hs.push(scope.spawn(move||{
     barrier.wait();let mut count=0;for j in 0..a.len(){let i=(j+t)%a.len();for &g in groups {let name=if t%2==0 {a[i]}else{b[i]};count+=direct_see(slots,shards,name,g,4,0);}}count
    }));}hs.into_iter().map(|h|h.join().unwrap()).sum()
   });assert_eq!(sum,(values.len()*groups.len()) as i64);
  }}
 }
}
