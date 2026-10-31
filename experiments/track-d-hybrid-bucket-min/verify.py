#!/usr/bin/env python3
"""Run the cached-min queue/forced-cap and independent graph oracles."""
import hashlib, subprocess, tempfile
from pathlib import Path
p=Path(__file__).resolve().parent; root=p.parents[1]; s=(p/'candidate.rs').read_text()
assert hashlib.sha256(s.encode()).hexdigest()=='628b0922b43babe854af632876ce43a328c3d5b82286157aa6d7b1bf5b8c81ef'
def run(*args): subprocess.run([str(x) for x in args],check=True)
with tempfile.TemporaryDirectory(prefix='sd-min-verify-') as d:
 d=Path(d); bins=[]; marker='const POOL_CAP: usize = 65_536;'; assert s.count(marker)==1
 for cap in (0,1,2,65536):
  src=d/f'cap{cap}.rs'; binary=d/f'cap{cap}'; src.write_text(s.replace(marker,f'const POOL_CAP: usize = {cap};'))
  run('rustc','--edition=2021','-O','-C','overflow-checks=yes','-C','debug-assertions=yes',src,'-o',binary); bins.append(binary)
 run('python3',p/'run-forced.py');run('python3',p/'run-pool-property.py');run('python3',p/'run-boundary.py')
 for test in ('oracle.py','exhaustive.py'):run('python3',root/'experiments/track-d-balanced-frontier'/test,*bins)
 run('python3',root/'experiments/track-d-u32-fallback/thresholds.py',*bins)
 for b in (bins[1],bins[3]):run('python3',root/'experiments/track-d-packed32-adj/boundaries.py',b)
print('PASS cached minima, cap exhaustion and graph oracles')
