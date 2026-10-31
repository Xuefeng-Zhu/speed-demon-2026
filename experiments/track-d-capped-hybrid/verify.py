#!/usr/bin/env python3
"""Build and compare default and deliberately tiny pool capacities. No datasets retained."""
import argparse,hashlib,subprocess,tempfile
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--cpu');p.add_argument('--extremes',action='store_true');a=p.parse_args()
here=Path(__file__).resolve().parent;root=here.parents[1];s=(here/'candidate.rs').read_text()
assert hashlib.sha256(s.encode()).hexdigest()=='671c639be3400209e83e080dfb54947affd30ca71dc34ec17804d24d70292d9c'
def run(*x): subprocess.run([str(z) for z in x],check=True)
with tempfile.TemporaryDirectory(prefix='d-hybrid-check-') as d:
 d=Path(d);bins=[];marker='const POOL_CAP: usize = 65_536;';assert s.count(marker)==1
 for cap in (0,1,2,65536):
  source=d/f'cap{cap}.rs';binary=d/f'cap{cap}'
  source.write_text(s.replace(marker,f'const POOL_CAP: usize = {cap};'))
  flags=['rustc','--edition=2021','-O','-C','overflow-checks=yes','-C','debug-assertions=yes']
  if a.cpu: flags+=['-C',f'target-cpu={a.cpu}']
  run(*flags,source,'-o',binary);bins.append(binary)
 run('python3',here/'run-forced.py');run('python3',here/'run-pool-property.py')
 for script in ('oracle.py','exhaustive.py'):run('python3',root/'experiments/track-d-balanced-frontier'/script,*bins)
 run('python3',root/'experiments/track-d-u32-fallback/thresholds.py',*bins)
 for binary in (bins[1],bins[3]):run('python3',root/'experiments/track-d-packed32-adj/boundaries.py',binary)
 if a.extremes:run('python3',root/'experiments/track-d-balanced-frontier/extremes.py',bins[1],bins[3])
print('PASS default and forced capacity checks')
