#[cfg(test)]
mod independent_singlemap_review {
 use super::*;
 use std::collections::HashSet;
 #[test]
 fn exact_collision_and_bitmap_boundaries() {
  let names: Vec<&'static [u8]> = ["", "a", "a ", "\"\"", "b", "a", "", "b"]
      .into_iter().map(|s| &*Box::leak(s.as_bytes().to_vec().into_boxed_slice())).collect();
  let gs=[0usize,1,62,63,64,65,126,127,128,129,190,191,192,193,254,255];
  let mut set=HashSet::new(); let mut owner=SmallOwner::default();
  for round in 0..4 {for &name in &names {for &g in &gs {
   let key=(name.to_vec(),g);
   assert_eq!(owner.see(name, 42, g), set.insert(key) as i64, "round={round} name={name:?} g={g}");
  }}}
  // Distinct prehash does not alter exact deduplication within each bucket.
  for h in 0..100 {for &g in &gs {
   let name=Box::leak(format!("n{h}").into_bytes().into_boxed_slice());
   assert_eq!(owner.see(name,h+100,g),1);
   assert_eq!(owner.see(name,h+100,g),0);
  }}
 }
}
#[test] fn independent_size() { eprintln!("SmallRow={} HashMap={} Event={}",std::mem::size_of::<SmallRow>(),std::mem::size_of::<HashMap<u64,SmallRow>>(),std::mem::size_of::<Event>()); }
