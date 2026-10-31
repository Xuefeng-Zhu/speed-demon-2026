
#[cfg(test)]
mod independent {
 use super::*;
 use std::time::Instant;
 #[test]
 fn event_key_exactness_and_layout() {
  assert_eq!(std::mem::size_of::<Event>(),16);
  let mut map:HashMap<Key,usize,BuildHasherDefault<Identity>>=HashMap::default();
  let a:&'static [u8]=Box::leak(b"same bytes".to_vec().into_boxed_slice());
  let b:&'static [u8]=Box::leak(b"same bytes".to_vec().into_boxed_slice());
  let other:&'static [u8]=Box::leak(b"same byteS".to_vec().into_boxed_slice());
  for h in [0,1,u64::MAX,0x123456789abcdef0] {
   map.clear();let x=Key{name:a,hash:h};let y=Key{name:b,hash:h};let z=Key{name:other,hash:h};
   assert_eq!(map.insert(x,10),None);assert_eq!(map.get(&y),Some(&10));assert_eq!(map.insert(y,11),Some(10));
   assert_eq!(map.insert(z,12),None);assert_eq!(map.len(),2);
   assert_eq!(map.get(&Key{name:a,hash:h}),Some(&11));assert_eq!(map.get(&Key{name:other,hash:h}),Some(&12));
  }
 }
 #[test]
 fn same_bytes_always_have_same_precomputed_hash_and_owner() {
  for size in [0usize,1,7,8,15,16,31,32,255,65534,65535,65536,131071] {
   let a=vec![b'a';size];let b=a.clone();let h=BuildHasherDefault::<Fx>::default().hash_one(a.as_slice());
   assert_eq!(h,BuildHasherDefault::<Fx>::default().hash_one(b.as_slice()));
   for parts in [1usize,2,3,7,12,32] {
    assert_eq!(((h as u128 * parts as u128)>>64) as usize,((BuildHasherDefault::<Fx>::default().hash_one(b.as_slice()) as u128 * parts as u128)>>64) as usize);
   }
  }
 }
 #[test]
 fn exact_collision_family_and_rotated_identity() {
  let mut map:HashMap<Key,usize,BuildHasherDefault<Identity>>=HashMap::default();
  for i in 0..2500usize {let name:&'static [u8]=Box::leak(format!("same hash name {i:04}").into_bytes().into_boxed_slice());assert_eq!(map.insert(Key{name,hash:0},i),None);}
  assert_eq!(map.len(),2500);
  for i in 0..2500usize {let s=format!("same hash name {i:04}");let name:&'static[u8]=Box::leak(s.into_bytes().into_boxed_slice());assert_eq!(map.get(&Key{name,hash:0}),Some(&i));}
  for h in [0,1,u64::MAX,0x123456789abcdef0] {let mut id=Identity::default();id.write_u64(h);assert_eq!(id.finish(),h.rotate_left(32));}
 }
 #[test]
 fn clustered_distinct_hashes_remain_exact_but_can_be_slow() {
  const N:usize=16_384;
  let values:Vec<_>=(0..N).map(|i| {
   let rotated=((i as u64 &255)<<20)|((i as u64>>8)<<32);
   let hash=rotated.rotate_right(32);assert_eq!(((hash as u128*12)>>64),0);
   let name:&'static [u8]=Box::leak(format!("name-{i:06}").into_bytes().into_boxed_slice());(name,hash)
  }).collect();
  let mut identity:HashMap<Key,usize,BuildHasherDefault<Identity>>=HashMap::default();let start=Instant::now();
  for (i,&(name,hash)) in values.iter().enumerate(){assert_eq!(identity.insert(Key{name,hash},i),None);}
  let identity_ns=start.elapsed().as_nanos();
  let mut salted:HashMap<Key,usize>=HashMap::new();let start=Instant::now();
  for (i,&(name,hash)) in values.iter().enumerate(){assert_eq!(salted.insert(Key{name,hash},i),None);}
  let salted_ns=start.elapsed().as_nanos();
  for (i,&(name,hash)) in values.iter().enumerate(){assert_eq!(identity.get(&Key{name,hash}),Some(&i));assert_eq!(salted.get(&Key{name,hash}),Some(&i));}
  println!("synthetic arbitrary prehashes, no claim of legal-name preimages: identity_ns={identity_ns} salted_ns={salted_ns} keys={N}");
 }
}
