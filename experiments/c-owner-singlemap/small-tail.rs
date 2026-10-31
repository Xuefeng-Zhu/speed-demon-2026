#[cfg(test)]
mod tests_small {
 use super::*; use std::collections::HashSet;
 #[test]
 fn collisions_and_all_group_words() {
  let names: Vec<&'static [u8]>=(0..50_000).map(|i|Box::leak(format!("name {i}").into_bytes().into_boxed_slice()) as &'static [u8]).collect();
  let mut dict=SmallOwner::default();let mut expected=HashSet::new();let mut r=0x12345abcdeu64;
  for i in 0..200_000 {r^=r<<13;r^=r>>7;r^=r<<17;let name=(r as usize)%names.len();let g=((r>>24) as usize)%256;
   let h=if name%2==0 {0}else{(name%11) as u64};
   assert_eq!(dict.see(names[name],h,g),expected.insert((name,g)) as i64,"iteration {i}");
  }
  for i in 0..names.len() { let h=if i%2==0{0}else{(i%11) as u64}; for g in [0usize,63,64,127,128,191,192,255] {
   assert_eq!(dict.see(names[i],h,g),expected.insert((i,g)) as i64);assert_eq!(dict.see(names[i],h,g),0);
  }}
 }
}
