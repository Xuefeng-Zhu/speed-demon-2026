#!/usr/bin/env python3
"""Test exact candidate plus an all-short-hashes-collide build."""
from pathlib import Path
import subprocess,tempfile
here=Path(__file__).resolve().parent
src=(here/'candidate.rs').read_text()
tail=(here/'property-tail.rs').read_text()
needle='    fn short_hash(mut x: u64) -> usize {\n'
assert src.count(needle)==1
forced=src.replace(needle,needle+'        let _ = x; return 0;\n',1)
# Forced-collision quadratic probing uses small controlled tables only.
forced_tail=tail.replace('0,1,255,4096,262_144,262_145','0,1,255,1024').replace('if n <= 262_144 {n} else {0}','if n <= 262_144 {n} else {0}')
with tempfile.TemporaryDirectory(prefix='b-compact-props-') as tmp:
 for name,body in [('normal',src+'\n'+tail),('forced',forced+'\n'+forced_tail)]:
  path=Path(tmp)/(name+'.rs'); path.write_text(body)
  binary=Path(tmp)/name
  subprocess.run(['rustc','--edition=2021','--test','-O','-C','overflow-checks=yes','-C','debug-assertions=yes',str(path),'-o',str(binary)],check=True)
  subprocess.run([str(binary),'--test-threads=1'],check=True)
