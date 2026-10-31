#!/usr/bin/env python3
"""Extract exact formatter and independently check rate/rank bounds."""
from pathlib import Path
import subprocess,tempfile
root=Path(__file__).resolve().parents[2]
s=(root/'experiments/a-format-u32/candidate.rs').read_text()
a=s.index('fn push_num(');b=s.index('\n}\n',a)+2
func=s[a:b]
tests=r'''
#[cfg(test)] mod independent {
 use super::*;
 fn check(n:u64,e:u64){
   assert!(n>0 && e<=n && n<=u32::MAX as u64);
   let r=e*1_000_000/n;
   let exact=(u128::from(e)*1_000_000/u128::from(n)) as u64;
   assert_eq!(r,exact);assert!(r<=1_000_000);
   let mut out=Vec::new();push_num(&mut out,n as u32);push_num(&mut out,e as u32);push_num(&mut out,r as u32);
   assert_eq!(out,format!(" {n} {e} {r}").as_bytes());
 }
 #[test] fn rate_and_rank_bounds(){
  for n in 1u64..=3_100_000 {
   for e in [0,1,n/2,n-1,n]{check(n,e);}
   let rank=|p:u64|(p*n+99)/100-1;
   let (a,b,c)=(rank(50),rank(95),rank(99));assert!(a<=b && b<=c && c<n);
   for p in [50u64,95,99] {assert_eq!(rank(p)+1,(p*n).div_ceil(100));}
  }
  for n in [u32::MAX as u64, u32::MAX as u64-1,2_147_483_648] {for e in [0,1,n/2,n-1,n] {check(n,e);}}
  let mut x=0x9e3779b97f4a7c15u64;
  for _ in 0..1_000_000 {x^=x<<13;x^=x>>7;x^=x<<17;let n=1+(x % (u32::MAX as u64));x^=x<<13;x^=x>>7;x^=x<<17;let e=x%(n+1);check(n,e);}
  println!("PASS 3.1M rank bounds, 15.5M boundary rates and 1M random rates, plus u32-max counts");
 }
}
'''
with tempfile.TemporaryDirectory() as d:
 p=Path(d)/'review.rs';out=Path(d)/'review';p.write_text(func+'\n'+tests)
 subprocess.run(['rustc','--edition=2021','--test','-O','-C','overflow-checks=yes',str(p),'-o',str(out)],check=True)
 subprocess.run([str(out),'--nocapture'],check=True)
