#[cfg(all(test,not(b_medium_crc_forced),any(all(target_arch="x86_64",target_feature="sse4.2"),b_medium_crc_emulate)))]
mod medium_threshold_review {
 use super::*;
 #[test] fn exact_threshold_boundaries() {
  let mut buckets:Vec<Vec<Vec<u8>>>=vec![Vec::new();256];
  for i in 0..1_000_000u32 {
   let w=format!("m{i:08x}").into_bytes();let k=key(&w,0,w.len());let bucket=medium_crc(k.0[0],k.0[1])&255;
   if buckets[bucket].len()<34 { buckets[bucket].push(w); }
   if buckets[1].len()>=34 && (224..256).chain(0..=32).all(|i|!buckets[i].is_empty()) && (100..230).step_by(2).filter(|&i|!buckets[i].is_empty()).count()>=32 { break; }
  }
  for (n,want) in [(33,true),(34,false)] {
   let mut words=buckets[1][..n].to_vec();
   for i in (100..230).step_by(2) {if words.len()==65 {break;} words.push(buckets[i][0].clone());}
   assert_eq!(words.len(),65);let mut p=Plan{slots:vec![MISS;1024],..Default::default()};
   let ids:Vec<_>=words.iter().map(|w|p.intern(w,IN_BOOL)).collect();p.build_short();p.build_medium();
   assert_eq!(p.medium_mode,want,"displacement threshold n={n}");
   for (w,id) in words.iter().zip(ids){assert_eq!(p.lookup_token(w,0,w.len()),id);}
  }
  for (end,want) in [(31,true),(32,false)] {
   let mut words:Vec<_>=(224..256).chain(0..=end).map(|i|buckets[i][0].clone()).collect();
   if words.len()==64 {words.push(buckets[100][0].clone());}
   assert_eq!(words.len(),65);let mut p=Plan{slots:vec![MISS;1024],..Default::default()};
   let ids:Vec<_>=words.iter().map(|w|p.intern(w,IN_BOOL)).collect();p.build_short();p.build_medium();
   assert_eq!(p.medium_mode,want,"cyclic run ending {end}");
   for (w,id) in words.iter().zip(ids){assert_eq!(p.lookup_token(w,0,w.len()),id);}
  }
  println!("PASS displacement 32/33 and cyclic occupied run 64/65 thresholds");
 }
}
