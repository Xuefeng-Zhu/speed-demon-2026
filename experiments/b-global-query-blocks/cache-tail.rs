#[cfg(test)]
mod concurrent_cache_test {
 use super::*;
 use std::sync::Barrier;
 fn included(doc:u32,term:usize)->bool { (doc.wrapping_mul(17).wrapping_add((term as u32)*13)%11)<5 }
 fn make_parts()->Vec<ChunkIndex> {
  let mut parts=Vec::new();let terms=64usize;
  for (first,n) in [(0u32,1usize),(1,62),(63,1),(64,1),(65,62),(127,1),(128,1),(129,71)] {
   let mut offs=Vec::new();let mut docs=Vec::new();offs.push(0);
   for t in 0..terms {for d in 0..n {if included(first+d as u32,t){docs.push(d as u32);}}offs.push(docs.len() as u32);}
   parts.push(ChunkIndex{first,ndocs:n,offs,docs,hits:Vec::new()});
  }
  parts
 }
 #[test] fn shared_cap_and_race() {
  const N:usize=200;const TERMS:usize=64;let words=N.div_ceil(64);let bytes=words*8;
  let parts=make_parts();
  for cap in [0usize,8,bytes*5,bytes*TERMS] {
   for _ in 0..12 {
    let cache=DenseCache::new(TERMS,cap);let barrier=Barrier::new(32);
    std::thread::scope(|scope| {
     for worker in 0..32 {let cache=&cache;let parts=&parts;let barrier=&barrier;scope.spawn(move ||{
      barrier.wait();for step in 0..TERMS {let t=(step*17+worker)%TERMS;
       if let Some(b)=cache.get(t,parts,words) {
        assert_eq!(b.len(),words);
        for d in 0..(words*64) {assert_eq!((b[d>>6]>>(d&63))&1,u64::from(d<N && included(d as u32,t)),"term={t},doc={d}");}
       }
      }
     });}
    });
    let actual=cache.slots.iter().filter(|s|matches!(s.get(),Some(Some(_)))).count();
    let denied=cache.slots.iter().filter(|s|matches!(s.get(),Some(None))).count();
    assert_eq!(actual+denied,TERMS);assert_eq!(cache.used.load(Ordering::Relaxed),actual*bytes);assert!(actual*bytes<=cap);
    assert_eq!(actual,(cap/bytes).min(TERMS));
   }
  }
  println!("PASS 48 cache races x 32 workers, quota=0/8/5 bitmaps/all, nonaligned chunk starts");
 }
}
