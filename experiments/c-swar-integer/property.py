#!/usr/bin/env python3
"""Compare exact integer parser with scalar for every legal seven-digit id."""
from pathlib import Path
import subprocess,tempfile
s=(Path(__file__).parent/'candidate.rs').read_text()
def get(name):
 i=s.index('fn '+name+'('); return s[i:s.index('\n}\n',i)+2]
main=r'''
fn main() {
    let mut c=0u64;
    for n in 1..=9_999_999u64 {
        let mut b=n.to_string().into_bytes();
        b.extend_from_slice(b",abcdefgh");
        let mut i=0; let v=positive_fast(&b,&mut i);
        assert_eq!(v as u64,n); assert_eq!(i,n.to_string().len()+1); c+=1;
    }
    for n in [10_000_000u64,39_999_999,1,9,10,99,100,999,1000,9_999_999] {
      for pad in 0..32 {
        for suffix in ["", "x", "abcdefghi", ",,,", "123456789"] {
          let b=format!("{}{n},{suffix}", "a".repeat(pad)).into_bytes();
          let (mut p,mut q)=(pad,pad); let v=positive_fast(&b,&mut p);let w=number(&b,&mut q);
          assert_eq!((v,p),(w,q)); c+=1;
        }
      }
    }
    println!("PASS {c} integer comparisons");
}
'''
with tempfile.TemporaryDirectory(prefix='c-swar-integer-') as td:
 p=Path(td); (p/'main.rs').write_text(get('number')+'\n'+get('positive_fast')+'\n'+main)
 subprocess.run(['rustc','--edition=2021','-O','-C','overflow-checks=yes',str(p/'main.rs'),'-o',str(p/'main')],check=True)
 subprocess.run([str(p/'main')],check=True)
