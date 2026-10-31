#!/usr/bin/env python3
"""Exercise exact owner mapping: range, reproducibility, extreme hashes."""
from pathlib import Path
import subprocess,tempfile
s=(Path(__file__).parent/'candidate.rs').read_text()
expr='((h as u128 * parts as u128) >> 64) as usize'
assert s.count(expr)==1
body='fn owner(h:u64, parts:usize)->usize { '+expr+' }\n'
main=r'''
fn main() {
 let mut x=0x34d195781f3ab5ceu64; let mut checks=0u64;
 for parts in 1..=1024usize {
  for h in [0,1,2,u64::MAX/2,u64::MAX-2,u64::MAX-1,u64::MAX] {
   let o=owner(h,parts);assert!(o<parts);assert_eq!(o,owner(h,parts));checks+=1;
  }
  assert_eq!(owner(0,parts),0);assert_eq!(owner(u64::MAX,parts),parts-1);
 }
 for _ in 0..1_000_000 {
  x^=x<<13;x^=x>>7;x^=x<<17;let h=x;
  x^=x<<13;x^=x>>7;x^=x<<17;let n=(x as usize%1024)+1;
  let o=owner(h,n);assert!(o<n);assert_eq!(o,owner(h,n));checks+=1;
 }
 println!("PASS {checks} owner-range and reproducibility checks");
}
'''
with tempfile.TemporaryDirectory(prefix='c-owner-prop-') as td:
 p=Path(td);(p/'main.rs').write_text(body+main)
 subprocess.run(['rustc','--edition=2021','-O','-C','overflow-checks=yes',str(p/'main.rs'),'-o',str(p/'main')],check=True)
 subprocess.run([str(p/'main')],check=True)
