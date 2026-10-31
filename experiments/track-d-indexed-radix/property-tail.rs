#[cfg(test)] mod indexed_heap_test {
 use super::*; use std::collections::BTreeSet;
 #[test] fn mixed_decrease_pop_and_clear() {
  const N: usize=257; let mut h=RadixHeap::new(N); let mut model=BTreeSet::new();
  let mut keys=[None;N]; let mut state=0x58f9_334d_a10b_182fu64;
  for step in 0..1_000_000 {
   state^=state<<13;state^=state>>7;state^=state<<17;
   if step%7193==0 { h.clear(); model.clear(); keys.fill(None); }
   if state%4==0 && !model.is_empty() {
    let k=h.top(|v|keys[v as usize].unwrap()).unwrap(); let (expected,_)=*model.first().unwrap();assert_eq!(k,expected);
    let (actual,v)=h.pop();assert_eq!(actual,expected);assert!(model.remove(&(actual,v)));keys[v as usize]=None;
   } else {
    let v=((state>>16)as usize)%N;let lower=h.last;
    let d=match keys[v] { Some(old) if old>lower => lower + (state%(old-lower)), Some(_) => continue, None => lower.saturating_add((state>>32)&0xffff_ffff) };
    if let Some(old)=keys[v] { h.remove(v as u32,old);assert!(model.remove(&(old,v as u32))); }
    keys[v]=Some(d);h.push(d,v as u32);assert!(model.insert((d,v as u32)));
   }
   assert_eq!(h.count,model.len());
   if step%97==0 {let got=h.top(|v|keys[v as usize].unwrap());assert_eq!(got,model.first().map(|x|x.0));}
  }
 }
}
