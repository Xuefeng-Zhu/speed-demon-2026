#!/usr/bin/env python3
from pathlib import Path
import subprocess,tempfile
root=Path(__file__).resolve().parents[2]
s=(root/'experiments/b-short-packed-tags/candidate.rs').read_text()
t=(root/'experiments/b-short-lookup/candidate-property.rs').read_text();t=t[t.index('#[cfg(test)]\nmod independent'):]
t+='\n'+(root/'experiments/b-short-packed-tags/threshold-tail.rs').read_text()
a='''    fn short_hash(mut x: u64) -> usize {
        x ^= x >> 30;
        x = x.wrapping_mul(0xbf58_476d_1ce4_e5b9);
        x ^= x >> 27;
        x = x.wrapping_mul(0x94d0_49bb_1331_11eb);
        ((x ^ (x >> 31)) >> 32) as usize
    }'''
assert s.count(a)==1
with tempfile.TemporaryDirectory() as d:
 for forced in (False,True):
  source=s.replace(a,'    fn short_hash(_x: u64) -> usize { 0 }') if forced else s
  tail=t.replace('run(100000)','run(5000)') if forced else t
  p=Path(d)/('forced.rs' if forced else 'normal.rs');p.write_text(source+'\n'+tail);b=p.with_suffix('')
  flags=['--cfg','forced_hash_test'] if forced else []
  subprocess.run(['rustc','--edition=2021','--test','-O','-C','overflow-checks=yes',*flags,str(p),'-o',str(b)],check=True)
  subprocess.run([str(b),'--nocapture'],check=True)
