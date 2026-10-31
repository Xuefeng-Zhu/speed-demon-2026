#!/usr/bin/env python3
"""Check the exact batch4 source and deliberately tiny/default pools."""
import hashlib, subprocess, tempfile
from pathlib import Path
here=Path(__file__).resolve().parent
root=here.parents[1]
src=(here/'batch4.rs').read_text()
assert hashlib.sha256(src.encode()).hexdigest() == 'fa36f3bbfa3ec9e6a92fd787ada415c5e257cdf1ea62a2a2fcf23718c3d5c1c0'
marker='const POOL_CAP: usize = 65_536;'
assert src.count(marker)==1
with tempfile.TemporaryDirectory(prefix='sd-batch15-') as td:
 p=Path(td); bins=[]
 for cap in (0,1,2,15,16,17,65536):
  s=p/f'c{cap}.rs'; b=p/f'c{cap}'
  s.write_text(src.replace(marker,f'const POOL_CAP: usize = {cap};'))
  subprocess.run(['rustc','--edition=2021','-O','-C','overflow-checks=yes','-C','debug-assertions=yes',str(s),'-o',str(b)],check=True)
  bins.append(str(b))
 for name in ('oracle.py','exhaustive.py'):
  subprocess.run(['python3',str(root/'experiments/track-d-balanced-frontier'/name),*bins],check=True)
 subprocess.run(['python3',str(root/'experiments/track-d-u32-fallback/thresholds.py'),*bins],check=True)
 subprocess.run(['python3',str(root/'experiments/track-d-packed32-adj/boundaries.py'),bins[-1]],check=True)
 subprocess.run(['python3',str(root/'experiments/track-d-balanced-frontier/extremes.py'),bins[1],bins[-1]],check=True)
 subprocess.run(['python3',str(here/'oracle4.py')],check=True)
print('PASS hybrid batch4 forced-cap/reference/boundary/extreme suites')
