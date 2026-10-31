#[cfg(test)] mod edge_review {
 use super::*;
 fn buckets(target:&[usize], each:usize, mask:usize)->Vec<Vec<Vec<u8>>> {
  let mut out=vec![Vec::new();mask+1];let mut needed=target.len()*each;
  for i in 0..2_000_000 {let w=format!("{i:07x}").into_bytes();let k=key(&w,0,w.len()).0[0];let b=short_crc(k)&mask;
   if target.contains(&b)&&out[b].len()<each{out[b].push(w);needed-=1;if needed==0{break}}
  }
  assert_eq!(needed,0);out
 }
 fn plan(words:Vec<Vec<u8>>)->Plan<'static> {
  let mut p=Plan{slots:vec![MISS;2048],..Default::default()};
  for w in &words {p.intern(w,IN_BOOL);}
  p.build_short();
  for w in &words {assert_ne!(p.lookup_token(w,0,w.len()),MISS);}
  assert_eq!(p.lookup_token(b"zzzzzzz",0,7),MISS);p
 }
 #[test] fn boundary_on_displacement() {
  let mut bs=buckets(&[0],34,127);let words=bs[0].drain(..).collect::<Vec<_>>();
  let p=plan(words[..33].to_vec());assert_eq!(p.short_slots.len(),128);assert!(p.short_crc_mode,"displacement 32 allowed");
  let p=plan(words);assert_eq!(p.short_slots.len(),128);assert!(!p.short_crc_mode,"displacement 33 forces fallback");
 }
 #[test] fn boundary_on_wrapping_cluster() {
  let mut wanted=(200..256).chain(0..=8).collect::<Vec<_>>();wanted.extend(20..=35);
  let mut bs=buckets(&wanted,1,255);let mut cluster=Vec::new();
  for b in (200..256).chain(0..=8) {cluster.push(bs[b].pop().unwrap());}
  let extra=(20..=35).map(|b|bs[b].pop().unwrap()).collect::<Vec<_>>();
  for (k,expected) in [(64,true),(65,false)] {let mut ws=cluster[..k].to_vec();ws.extend_from_slice(&extra);let p=plan(ws);
   assert_eq!(p.short_slots.len(),256);assert_eq!(p.short_crc_mode,expected,"cluster {k}");}
 }
 #[test] fn empty_table_and_only_long_terms() {
  let mut p=Plan{slots:vec![MISS;32],..Default::default()};p.build_short();assert!(p.short_crc_mode);assert_eq!(p.lookup_token(b"a",0,1),MISS);
  p.intern(b"abcdefghi",IN_BOOL);p.build_short();assert!(p.short_crc_mode);assert_eq!(p.lookup_token(b"a",0,1),MISS);assert_ne!(p.lookup_token(b"abcdefghi",0,9),MISS);
 }
}
