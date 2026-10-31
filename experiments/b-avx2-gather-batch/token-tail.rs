#[cfg(test)]
mod independent_transition {
 use super::*;
 #[cfg(all(target_arch="x86_64", target_feature="avx2"))]
 #[test] fn actual_avx2_enabled() { assert!(std::arch::is_x86_feature_detected!("avx2")); }
 fn expected(data:&[u8],p:&Plan)->Vec<u32> {
  let mut out=Vec::new(); let mut start=None;
  for i in 0..=data.len() {
   let word=i<data.len() && data[i].is_ascii_alphanumeric();
   if word { if start.is_none() { start=Some(i); } }
   else if let Some(s)=start.take() { let n=i-s; out.push(if n<=32 { p.lookup_token(data,s,n) } else { MISS }); }
  }
  out
 }
 #[test]
 fn masks_and_boundaries() {
  let mut p=Plan{slots:vec![MISS;256],..Default::default()};
  for n in 1..=32 { p.intern(&vec![b'a';n],IN_BOOL); }
  p.intern(b"b0c",IN_BOOL);p.intern(b"x",IN_BOOL);p.build_short();
  let mut bytes=Vec::new(); let mut ranges=Vec::new();
  for offset in [0usize,15,16,17,31,32] {
   for mask in 0..65536u32 {
    bytes.extend_from_slice(b"0\t"); let start=bytes.len();
    bytes.extend(std::iter::repeat(b'!').take(offset));
    for i in 0..16 { bytes.push(if mask & (1<<i)!=0 {if i%2==0 {b'A'} else {b'a'}} else {b'-'}); }
    bytes.extend_from_slice(b"aAAA!b0C!X");
    ranges.push((start,bytes.len())); bytes.push(b'\n');
   }
  }
  let mut state=0x3141592653589793u64;
  for _ in 0..100000 {
   bytes.extend_from_slice(b"0\t");let start=bytes.len();
   for _ in 0..128 { state^=state<<13;state^=state>>7;state^=state<<17;bytes.push(if state&3!=0 {b'a'} else {b'!'}); }
   ranges.push((start,bytes.len()));bytes.push(b'\n');
  }
  let mut doc=0usize;
  for_each_doc(&bytes,0,bytes.len(),&p,|tokens|{
    let (lo,hi)=ranges[doc];
    assert_eq!(tokens,expected(&bytes[lo..hi],&p),"document {doc}");doc+=1;
  });
  assert_eq!(doc,ranges.len());
  println!("PASS {} exhaustive-mask and random 32-byte boundary documents",doc);
 }
}
