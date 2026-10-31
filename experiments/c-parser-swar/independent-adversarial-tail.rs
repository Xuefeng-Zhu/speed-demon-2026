
#[test]
fn exhaustive_positive_numbers_and_boundaries() {
 for v in 1..=9_999_999u64 {
   let text=v.to_string();
   let mut b=Vec::from(text.as_bytes()); b.extend_from_slice(b",-ZZZZZZZZ");
   let mut p=0; assert_eq!(positive_fast(&b,&mut p),v as i64); assert_eq!(p,text.len()+1);
 }
 for v in [10_000_000u64, 39_999_999, 40_000_000, 99_999_999, 999_999_999, 4_000_000_000] {
   let text=v.to_string(); for prefix in 0..16 { for tail in [b"".as_slice(), b"\\\"foo\",bar", b"-......." ] {
     let mut b=vec![b'x';prefix];b.extend_from_slice(text.as_bytes());b.push(b',');b.extend_from_slice(tail);
     let mut p=prefix; assert_eq!(positive_fast(&b,&mut p),v as i64);assert_eq!(p,prefix+text.len()+1);
   }}
 }
}
#[test]
fn delimiter_exact_over_padding_borrows_and_alignments() {
 for delim in [b',',b'"'] { for pre in 0..16 { for width in 0..80 { for c in 0u8..=255 {
   if c == delim { continue; }
   let mut b=vec![b'A';pre];b.resize(pre+width,c);b.push(delim);b.extend([delim.wrapping_add(1);16]);
   assert_eq!(field_delim(&b,pre,delim), pre+width, "delim={delim} pre={pre} width={width} byte={c}");
 }}}}
 let mut x=0xdeadbeefcafeu64;
 for _ in 0..200_000 {
   x ^= x << 13;x ^= x >> 7;x ^= x << 17; let width=(x as usize)%200;
   let mut b=Vec::with_capacity(width+32);for _ in 0..width {x^=x<<13;x^=x>>7;x^=x<<17;b.push((x&255) as u8)}
   b.push(b',');let expected=b.iter().position(|c|*c==b',').unwrap();assert_eq!(field_delim(&b,0,b','),expected);
 }
}
#[test]
fn encoded_field_roundtrip() {
 for input in ["", "a", "the words  ", "Kaphar, Titus", "Ann \"Annie\" Lee", "\"", "\"\"", "a\nline, \"and quote\""] {
   for quoted in [false,true] {
     if !quoted && (!input.is_empty() && (input.contains(',') || input.contains('"') || input.contains('\n'))) {continue;}
     let encoded=if quoted {format!("\"{}\",z",input.replace('"',"\"\""))} else {format!("{},z",input)};
     let d: &'static [u8]=Box::leak(encoded.into_bytes().into_boxed_slice());let mut p=0; let (raw,len)=field(d,&mut p);
     assert_eq!(len as usize,input.len());assert_eq!(String::from_utf8_lossy(raw).replace("\"\"","\""),input);assert_eq!(d[p],b'z');
   }
 }
}
