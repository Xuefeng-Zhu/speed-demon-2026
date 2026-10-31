#[cfg(test)] mod fused_review {
 use super::*;
 fn check(raw: &[u8], quote: bool, prefix: usize, tail: usize) {
  let mut buf=vec![b'Z';prefix];
  if quote {buf.push(b'"');} buf.extend_from_slice(raw); if quote {buf.push(b'"');} buf.push(b','); buf.extend(std::iter::repeat(b'Z').take(tail));
  let data: &'static [u8]=Box::leak(buf.into_boxed_slice());
  let (mut p,mut q)=(prefix,prefix);let (expected,elen)=field(data,&mut p);let (got,glen,h)=field_name_hash(data,&mut q);
  assert_eq!((got,glen,q),(expected,elen,p));assert_eq!(h,name_hash(expected));
 }
 #[test] fn empty_and_unescaped_boundaries() {
  for len in 0..=256 {for prefix in 0..=15 {for tail in 0..=12 {let raw=vec![b'a';len];check(&raw,true,prefix,tail);if len==0 {check(&raw,false,prefix,tail);}}}}
  for len in [65534usize,65535,65536,131071] {let raw=vec![b'a';len];check(&raw,true,0,4);}
 }
 #[test] fn escapes_every_alignment() {
  for len in 2..=128 {for pos in 0..len-1 {let mut raw=vec![b'z';len];raw[pos]=b'"';raw[pos+1]=b'"';for prefix in 0..8 {check(&raw,true,prefix,8);}}}
 }
 #[test] fn true_empty_encoding_is_identical() {
  let mut q=0;let (a,_,h1)=field_name_hash(b"\"\",rest",&mut q);
  let mut p=0;let (b,_,h2)=field_name_hash(b",rest",&mut p);
  assert_eq!(a,b);assert_eq!(h1,h2);
 }
}
