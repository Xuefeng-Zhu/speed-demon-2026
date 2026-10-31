#[cfg(test)]
mod compact_record_properties {
 use super::*;
 #[test] fn exact_encoding_and_escape_order() {
  let latencies=[0u64,1,1_048_573,1_048_574,1_048_575,1_048_576,4_294_967_294,4_294_967_295];
  let statuses=[499u64,500,599];
  let mut data=Vec::new();
  for id in 0..2060u64 { for lat in latencies { for status in statuses {
   data.extend_from_slice(format!("2026-10-30T18:00:00.000000Z GET /id/{id:04} {status} {lat}\n").as_bytes());
  }}}
  let end=data.len();data.resize(end+4096,0);let chunk=parse(&data,0,end);
  assert_eq!(chunk.table.names.len(),2060);let mut seq=chunk.hours[0].iter();let mut esc=chunk.escapes[0].iter();let mut n=0usize;
  for id in 0..2060u64 { for lat in latencies { for status in statuses {
   let packed=*seq.next().unwrap();let error=u64::from(status>=500);let should_escape=id>=2048||lat>=1_048_575;
   assert_eq!(packed==u32::MAX,should_escape,"id={id} lat={lat} status={status}");
   let actual=if should_escape{*esc.next().unwrap()}else{u64::from(packed>>21)<<33 | u64::from((packed>>20)&1)<<32 | u64::from(packed&0x000f_ffff)};
   assert_eq!(actual,id<<33 | error<<32 | lat);n+=1;
  }}}
  assert!(seq.next().is_none());assert!(esc.next().is_none());
  println!("PASS {n} exact record encodings and escape ordering");
 }
}
