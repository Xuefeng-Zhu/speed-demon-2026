#!/usr/bin/env python3
import hashlib, subprocess, tempfile
from pathlib import Path
here=Path(__file__).resolve().parent
root=here.parents[1]
src=(here/'candidate.rs').read_text()
assert hashlib.sha256(src.encode()).hexdigest() == '343d15472ae055432dce4d4c4bbddb4b6483c061e66f613bd35ee6defeea1ca0'
marker='const POOL_CAP: usize = 65_536;'
assert src.count(marker)==1
with tempfile.TemporaryDirectory(prefix='sd-d-pool-bitmap-') as td:
 p=Path(td); bins=[]
 for cap in (0,1,2,65536):
  s=p/f'c{cap}.rs'; b=p/f'c{cap}'
  s.write_text(src.replace(marker,f'const POOL_CAP: usize = {cap};'))
  subprocess.run(['rustc','--edition=2021','-O','-C','overflow-checks=yes','-C','debug-assertions=yes',str(s),'-o',str(b)],check=True)
  bins.append(str(b))
 for name in ('oracle.py','exhaustive.py'):
  subprocess.run(['python3',str(root/'experiments/track-d-balanced-frontier'/name),*bins],check=True)
 subprocess.run(['python3',str(root/'experiments/track-d-u32-fallback/thresholds.py'),*bins],check=True)
 subprocess.run(['python3',str(root/'experiments/track-d-packed32-adj/boundaries.py'),bins[-1]],check=True)
 subprocess.run(['python3',str(root/'experiments/track-d-balanced-frontier/extremes.py'),bins[1],bins[-1]],check=True)
print('PASS forced-cap/reference/boundary/extreme suites')
