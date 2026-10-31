#[cfg(test)]
mod exact_format_property {
 use super::*;
 #[test] fn u32_decimal_and_sequences() {
  let mut out=Vec::new();
  for n in 0u32..=1_000_000 { out.clear();push_num(&mut out,n);assert_eq!(out,format!(" {n}").as_bytes()); }
  let mut seed=0x7f4a7c159e3779b9u64;
  for _ in 0..2_000_000 {
   seed^=seed<<13;seed^=seed>>7;seed^=seed<<17;let n=seed as u32;
   out.clear();push_num(&mut out,n);assert_eq!(out,format!(" {n}").as_bytes());
  }
  let mut power=1u32;
  loop {
   for n in [power.saturating_sub(1),power,power.saturating_add(1)] {out.clear();push_num(&mut out,n);assert_eq!(out,format!(" {n}").as_bytes());}
   match power.checked_mul(10){Some(v)=>power=v,None=>break}
  }
  out.clear();for n in [0,u32::MAX,1,10,999999,1000000] {push_num(&mut out,n);}
  assert_eq!(out,b" 0 4294967295 1 10 999999 1000000");
  println!("PASS 3,000,001 exhaustive/random u32 decimal values, powers and sequences");
 }
}
