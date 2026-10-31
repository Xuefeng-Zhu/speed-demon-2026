#[cfg(test)]
mod direct_many {
 use super::*;use std::sync::{Barrier,atomic::AtomicPtr};
 #[test]
 fn fifty_thousand_names_one_slot_and_group(){
  let values:Vec<&'static[u8]>=(0..50_000).map(|i| &*Box::leak(format!("name {i}").into_bytes().into_boxed_slice()) as &'static[u8]).collect();
  let shards:Vec<DirectShard>=(0..1024).map(|_|DirectShard::default()).collect();
  let slots:Vec<AtomicPtr<DirectNode>>=vec![AtomicPtr::new(std::ptr::null_mut())];
  let barrier=Barrier::new(8);let total:i64=thread::scope(|sc|{
   let mut h=Vec::new();for t in 0..8{let (values,shards,slots,barrier)=(&values,&shards,&slots,&barrier);h.push(sc.spawn(move||{
    barrier.wait();let mut total=0;for j in 0..values.len(){let i=(j+t*6341)%values.len();total+=direct_see(slots,shards,values[i],0,1,0);}total
   }));}h.into_iter().map(|x|x.join().unwrap()).sum()
  });assert_eq!(total,values.len() as i64);
 }
}
