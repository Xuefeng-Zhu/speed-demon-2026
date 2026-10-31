#!/usr/bin/env python3
"""Verify fused B scanner line/token boundaries on multiple worker counts."""
import argparse
import os
from pathlib import Path
import random
import subprocess
import sys
import tempfile

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('source',type=Path)
p.add_argument('reference',type=Path)
a=p.parse_args()
source=a.source.resolve().read_text()
reference=a.reference.resolve()
needle='let nthreads = thread::available_parallelism().map_or(4, |n| n.get());'
if source.count(needle)!=1:raise SystemExit('unexpected worker-count expression')

with tempfile.TemporaryDirectory(prefix='b-fused-independent-') as tmp:
 root=Path(tmp)
 workers=(1,2,3,7,12,32)
 for n in workers:
  src=root/f'w{n}.rs';src.write_text(source.replace(needle,f'let nthreads = {n};'))
  subprocess.run(['rustc','--edition=2021','-O','-C','overflow-checks=yes',str(src),'-o',str(root/f'w{n}')],check=True)
 rng=random.Random(55312)
 for case in range(20):
  case_dir=root/f'case{case}';data=case_dir/'data';ref=case_dir/'ref';data.mkdir(parents=True);ref.mkdir()
  texts=[]
  # Text boundaries move each newline, token start/end and next ID across all
  # 32-byte SIMD lanes. Include empty lines of text and long token runs.
  for prefix in range(64):
   for n in (0,1,2,7,8,9,15,16,17,30,31,32):
    tok=(b'A' if (prefix+case)&1 else b'0')*n
    suffix=(b'!X x 00' if (prefix+n)&1 else b'\xc3\xa9-Word')
    texts.append(b'!'*prefix+tok+suffix)
  for n in (0,1,30,31,32,33,62,63,64,65,94,95,96,97,127,128,129,1023):
   texts.extend((b'!'*n,b'A'*n,b'!'*n+b'A'*32,b'0'*min(n,32)))
  alphabet=[b'a',b'B',b'0',b'9',b'!',b' ',b'/',b'\xc3\xa9',b'\xf0\x9d\x94\x84']
  for _ in range(150):texts.append(b''.join(rng.choice(alphabet) for _ in range(rng.randrange(0,120))))
  if case==0:texts=[]
  with (data/'docs.txt').open('wb') as f:
   for i,text in enumerate(texts):f.write(str(i).encode()+b'\t'+text+b'\n')
  words=['a','b','word','x','0','00']+['a'*n for n in range(2,33)]+['0'*n for n in range(2,33)]
  queries=['BOOL '+w for w in words]
  queries+=['PHRASE "'+x+' '+y+'"' for x in words[:18] for y in words[:10]]
  queries+=['BOOL a OR 0 NOT x','BOOL a AND word OR 00','PHRASE "x x"']
  (data/'queries.txt').write_text('\n'.join(queries)+'\n')
  subprocess.run([sys.executable,str(reference),'--data',str(data),'--out',str(ref)],check=True,stdout=subprocess.DEVNULL)
  expected=(ref/'results.txt').read_bytes()
  for n in workers:
   out=case_dir/f'out{n}';out.mkdir()
   subprocess.run([str(root/f'w{n}')],env=dict(os.environ,SD_DATA=str(data),SD_OUT=str(out)),check=True)
   if (out/'results.txt').read_bytes()!=expected:raise SystemExit(f'FAIL case={case} workers={n}')
print(f'PASS 20 corpora x {len(workers)} worker counts against reference')
