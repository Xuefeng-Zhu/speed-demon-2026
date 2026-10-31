#[cfg(test)]
mod independent {
 use super::*;
 use std::collections::HashMap;
 fn word(mut v:u64,n:usize)->Vec<u8>{let mut o=vec![b'a';n]; for c in o.iter_mut().rev(){*c=b'a'+(v%26) as u8;v/=26;}o}
 fn run(n:usize){
  let mut p=Plan::default();p.slots=vec![MISS;(n*4).max(1).next_power_of_two()];let mut expected=HashMap::new();
  for i in 0..n { let len=1+(i%32); let mut s=word((i as u64).wrapping_mul(2654435761),len); if len>12 && i%4==0 {s[..8].copy_from_slice(b"aaaaaaaa");} let id=p.intern(&s,IN_BOOL);expected.insert(s,id); }
  p.build_short();
  for (s,&id) in &expected {
   assert_eq!(p.lookup_token(s,0,s.len()),id,"present {:?}",s);
   let mut t=vec![b'!'];t.extend(s.iter().map(|b|b.to_ascii_uppercase()));t.extend_from_slice(b"!nonsense");assert_eq!(p.lookup_token(&t,1,s.len()),id,"case");
  }
  for i in 0..n {let len=1+((i*7+3)%32);let s=word((i as u64).wrapping_mul(0x9e3779b97f4a7c15),len);let want=expected.get(&s).copied().unwrap_or(MISS);assert_eq!(p.lookup_token(&s,0,len),want,"absent {:?}",s);}
  let empty=Plan{slots:vec![MISS],..Default::default()};let mut p=empty;p.build_short();assert_eq!(p.lookup_token(b"a",0,1),MISS);
 }
 #[test]fn property(){run(100000)}
}
