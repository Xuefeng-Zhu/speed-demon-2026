#[cfg(all(test, any(all(target_arch="x86_64",target_feature="sse4.2"),b_medium_crc_emulate)))]
mod medium_review {
 use super::*;
 #[test]
 fn exact_keys_and_fallback() {
  let mut plan=Plan{slots:vec![MISS;8192],..Default::default()};
  let mut keys=Vec::new();
  for i in 0..1000 { let w=format!("a{i:015}").into_bytes(); let id=plan.intern(&w,IN_BOOL); keys.push((w,id)); }
  for n in [1usize,8,9,10,15,16,17,31,32] { let w=vec![b'z';n];let id=plan.intern(&w,IN_BOOL);keys.push((w,id)); }
  plan.build_short();plan.build_medium();
  #[cfg(not(b_medium_crc_forced))] assert!(plan.medium_mode,"normal CRC trial should accept this varied set");
  #[cfg(b_medium_crc_forced)] assert!(!plan.medium_mode,"constant CRC for >33 medium keys must fall back");
  let mut checks=0;
  for (w,id) in &keys {for pad in 0..32 {for tail in [b"".as_slice(),b"junk".as_slice(),b"!".as_slice()] {
   let mut data=vec![b'!';pad];data.extend(w.iter().map(|b|b.to_ascii_uppercase()));data.extend_from_slice(tail);
   assert_eq!(plan.lookup_token(&data,pad,w.len()),*id,"word {w:?}, offset {pad}");checks+=1;
  }}}
  for n in [9usize,10,15,16,17,32] {let w=vec![b'q';n];assert_eq!(plan.lookup_token(&w,0,w.len()),MISS);checks+=1;}
  let mut empty=Plan{slots:vec![MISS],..Default::default()};empty.build_short();empty.build_medium();assert!(empty.medium_mode);
  for n in [9usize,10,15,16] {let w=vec![b'a';n];assert_eq!(empty.lookup_token(&w,0,n),MISS);checks+=1;}
  println!("PASS {checks} medium/long keys, case, padding, alignment and fallback checks");
 }
}
