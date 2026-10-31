
#[cfg(test)]
mod independent {
 use super::*;
 #[test]
 fn packed_event_layout_and_reconstruction() {
  assert_eq!(std::mem::size_of::<Event>(),8);
  for len in [0usize,1,7,8,31,32,65534,65535,65536,131071] {
   let mut raw=vec![b'a';len];
   if len>=6 {raw[1]=b'"';raw[2]=b'"';raw[len-1]=b' ';}
   let mut bytes=vec![b'"'];bytes.extend_from_slice(&raw);bytes.extend_from_slice(b"\",tail");
   let recs: &'static [u8]=Box::leak(bytes.into_boxed_slice());
   let mut at=0;let (name,_)=field(recs,&mut at);assert_eq!(name,raw);
   let ev=Event{offset:1,len:u16::try_from(name.len()).unwrap_or(u16::MAX),group:65534};
   assert_eq!(event_name(recs,ev),raw,"length {len}");assert_eq!(ev.group as usize,65534);
  }
 }
 #[test]
 fn sentinel_unquoted_defensive_path() {
  let mut bytes=vec![b'x';65536];bytes.extend_from_slice(b",tail");
  let recs:&'static[u8]=Box::leak(bytes.into_boxed_slice());
  let ev=Event{offset:0,len:u16::MAX,group:0};assert_eq!(event_name(recs,ev),&recs[..65536]);
 }
 #[test]
 fn identical_bytes_always_route_to_same_owner() {
  for i in 0..1000usize {
   let x=format!("Name {i:04} with trailing ");
   let a:&'static[u8]=Box::leak(x.clone().into_bytes().into_boxed_slice());
   let b:&'static[u8]=Box::leak(x.into_bytes().into_boxed_slice());
   let h1=BuildHasherDefault::<Fx>::default().hash_one(a);let h2=BuildHasherDefault::<Fx>::default().hash_one(b);assert_eq!(h1,h2);
   for n in [1usize,2,3,7,12,32] {assert_eq!(((h1 as u128*n as u128)>>64) as usize,((h2 as u128*n as u128)>>64) as usize);}
  }
 }
 #[test]
 fn owner_assignment_is_exact_partition() {
  for n in 1usize..=1000 { let mut visited=vec![0;n];
   for t in 0..n {for b in (t..n).step_by(n) {visited[b]+=1;}}
   assert!(visited.iter().all(|&v|v==1));
   assert_eq!(((u64::MAX as u128*n as u128)>>64) as usize,n-1);
   for k in 1..n {let first=(((k as u128)<<64)+n as u128-1)/(n as u128);
    assert_eq!(((first*n as u128)>>64) as usize,k);
    assert_eq!((((first-1)*n as u128)>>64) as usize,k-1);
   }
  }
 }
 #[test]
 fn packed_gating_boundaries() {
  assert!(can_pack(MAX_PACKED_FILE,MAX_PACKED_GROUPS-1));
  assert!(!can_pack(MAX_PACKED_FILE+1,MAX_PACKED_GROUPS-1));
  assert!(!can_pack(MAX_PACKED_FILE,MAX_PACKED_GROUPS));
 }
}
