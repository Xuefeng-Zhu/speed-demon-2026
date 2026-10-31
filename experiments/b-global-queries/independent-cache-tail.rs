#[cfg(test)]
mod independent_cache_review {
 use super::*;
 use std::sync::Barrier;
 fn make_part(first:u32,n:usize,terms:usize)->ChunkIndex {
  let mut offs=vec![0u32];let mut docs=Vec::new();
  for t in 0..terms {let mut v=vec![(t%n) as u32,(n-1) as u32];v.sort();v.dedup();docs.extend(v);offs.push(docs.len() as u32);}
  ChunkIndex{first,ndocs:n,offs,docs,hits:Vec::new()}
 }
 #[test]
 fn concurrent_reservation_and_publication() {
  let terms=256;let parts=vec![make_part(0,65,terms),make_part(65,64,terms)];let words=3usize;
  let cache=DenseCache::new(terms,words*8*7+13);let gate=Barrier::new(16);
  std::thread::scope(|scope|{
   for worker in 0..16 {let cache=&cache;let parts=&parts;let gate=&gate;scope.spawn(move || {
    gate.wait();
    for i in 0..terms {
     let term=(i*73+worker*19)%terms;
     if let Some(bitmap)=cache.get(term,parts,words){
      let mut want=[0u64;3];
      for part in parts {for &d in &part.docs[part.offs[term] as usize..part.offs[term+1] as usize]{let d=part.first+d;want[d as usize>>6]|=1u64<<(d&63);}}
      assert_eq!(bitmap,&want);
     }
    }
   });}
  });
  assert_eq!(cache.used.load(Ordering::Relaxed),words*8*7);assert!(cache.used.load(Ordering::Relaxed)<=cache.limit);
  let mut yes=0;let mut no=0;
  for cell in &cache.slots {match cell.get().unwrap(){Some(_)=>yes+=1,None=>no+=1}}
  assert_eq!((yes,no),(7,249));
  let zero=DenseCache::new(terms,0);assert!(zero.get(0,&parts,words).is_none());assert_eq!(zero.used.load(Ordering::Relaxed),0);
  println!("PASS 16 threads, exact 7-of-256 cap, coherent values, publication and zero-cap fallback");
 }
}
