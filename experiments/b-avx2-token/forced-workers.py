#!/usr/bin/env python3
"""Compile temporary worker-count variants and run portable independent reference suite."""
import subprocess, sys, tempfile
from pathlib import Path
root=Path(__file__).resolve().parent
source=(root/'candidate.rs').read_text()
needle='let nthreads = thread::available_parallelism().map_or(4, |n| n.get());'
assert source.count(needle)==1
with tempfile.TemporaryDirectory(prefix='b-avx2-workers-') as tmp:
 p=Path(tmp)
 for n in (1,2,3,7,12,32):
  src=p/f'w{n}.rs'; exe=p/f'w{n}'
  src.write_text(source.replace(needle,f'let nthreads = {n};'))
  subprocess.run(['rustc','--edition=2021','-C','opt-level=3','-C','target-cpu=x86-64-v3',str(src),'-o',str(exe)],check=True)
  subprocess.run([sys.executable,str(root/'independent-review.py'),str(exe)],cwd=root,check=True)
 print('PASS six forced worker counts')
