#!/usr/bin/env python3
"""Check the exact min-key function on random and edge-case heap buckets."""
from pathlib import Path
import subprocess,tempfile
source=Path(__file__).with_name('meeting.rs').read_text()
tests=r'''
#[cfg(test)] mod t {
 use super::*;
 #[test] fn min_property() {
  let mut seed=0xfedcba9876543210u64;
  for n in 1..=1025 {
    for case in 0..64 {
      let mut v=Vec::new();
      for i in 0..n {
        seed^=seed<<13;seed^=seed>>7;seed^=seed<<17;
        let key=match (i+case)%13 {0=>u64::MAX,1=>0,2=>u32::MAX as u64,_=>seed};
        v.push(Item{key,node:i as u32,initialized_padding:0});
      }
      assert_eq!(min_key(&v),v.iter().map(|x|x.key).min().unwrap());
    }
  }
 }
}
'''
with tempfile.TemporaryDirectory(prefix='d-vector-property-') as tmp:
 p=Path(tmp); (p/'test.rs').write_text(source+tests)
 subprocess.run(['rustc','--edition=2021','-O','-C','overflow-checks=yes','--test',str(p/'test.rs'),'-o',str(p/'test')],check=True)
 subprocess.run([str(p/'test')],check=True)
