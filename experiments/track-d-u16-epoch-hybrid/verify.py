#!/usr/bin/env python3
"""Run debug/overflow caps, epoch-wrap unit, graph oracles, and optional extremes."""
from pathlib import Path
import argparse, hashlib, subprocess, tempfile
p=argparse.ArgumentParser();p.add_argument('--extremes',action='store_true');a=p.parse_args()
here=Path(__file__).resolve().parent;root=here.parents[1];source=(here/'candidate.rs').read_text(); tail=(here/'epoch-tail.rs').read_text()
marker='const POOL_CAP: usize = 65_536;';assert source.count(marker)==1
with tempfile.TemporaryDirectory(prefix='d-epoch-hybrid-') as d:
 d=Path(d);bins=[]
 for cap in (0,1,2,65536):
  s=d/f'cap{cap}.rs';b=d/f'cap{cap}';u=d/f'unit{cap}';s.write_text(source.replace(marker,f'const POOL_CAP: usize = {cap};'))
  flags=['rustc','--edition=2021','-O','-C','overflow-checks=yes','-C','debug-assertions=yes']
  subprocess.run([*flags,str(s),'-o',str(b)],check=True); bins.append(b)
  s.write_text(s.read_text()+'\n'+tail);subprocess.run([*flags,'--test',str(s),'-o',str(u)],check=True);subprocess.run([str(u)],check=True)
 for script in ('oracle.py','exhaustive.py'):
  subprocess.run(['python3',str(root/'experiments/track-d-balanced-frontier'/script),*map(str,bins)],check=True)
 subprocess.run(['python3',str(root/'experiments/track-d-u32-fallback/thresholds.py'),*map(str,bins)],check=True)
 for b in (bins[1],bins[3]):subprocess.run(['python3',str(root/'experiments/track-d-packed32-adj/boundaries.py'),str(b)],check=True)
 if a.extremes:subprocess.run(['python3',str(root/'experiments/track-d-balanced-frontier/extremes.py'),str(bins[1]),str(bins[3])],check=True)
print('PASS caps, epoch wrap/side state/fallback, random/exhaustive, cutoff and boundaries')
