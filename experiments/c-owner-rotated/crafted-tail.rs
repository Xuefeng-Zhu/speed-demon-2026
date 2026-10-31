
#[cfg(test)]
mod crafted {
 use super::*;
 use std::time::Instant;
 #[test]
 fn valid_ascii_names_same_owner_and_low_buckets() {
  const TARGET: usize=4096;
  let mut values=Vec::new();let mut examined=0u64;
  while values.len()<TARGET && examined < 120_000_000 {
   let mut name=[b'A';10];let mut v=examined;
   for x in &mut name[1..] { *x=b'A'+(v%26) as u8;v/=26; }
   let h=BuildHasherDefault::<Fx>::default().hash_one(name.as_slice());
   if (h >> 60)==0 && ((h >> 32)&1023)==0 {
    assert_eq!(((h as u128*12)>>64),0);
    let x:&'static [u8]=Box::leak(name.to_vec().into_boxed_slice());values.push((x,h));
   }
   examined+=1;
  }
  assert_eq!(values.len(),TARGET,"not enough legal names found after {examined}");
  let mut original:HashMap<&'static [u8],usize,BuildHasherDefault<Fx>>=HashMap::default();
  let start=Instant::now();for (i,&(name,_)) in values.iter().enumerate(){assert_eq!(original.insert(name,i),None)}let t_original=start.elapsed();
  let mut candidate:HashMap<Key,usize,BuildHasherDefault<Identity>>=HashMap::default();
  let start=Instant::now();for (i,&(name,hash)) in values.iter().enumerate(){assert_eq!(candidate.insert(Key{name,hash},i),None)}let t_candidate=start.elapsed();
  for (i,&(name,hash)) in values.iter().enumerate(){assert_eq!(candidate.get(&Key{name,hash}),Some(&i));assert_eq!(original.get(name),Some(&i));}
  println!("legal ASCII names={TARGET} examined={examined}; baseline_ns={} rotated_ns={} (one native insertion trial)",t_original.as_nanos(),t_candidate.as_nanos());
 }
}
