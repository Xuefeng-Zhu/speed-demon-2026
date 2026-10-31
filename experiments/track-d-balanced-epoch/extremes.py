#!/usr/bin/env python3
"""Full-size max-weight chain, unreachable and repeated-query extreme cases."""
import argparse,os,subprocess,tempfile
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__);p.add_argument('binaries',nargs='+');a=p.parse_args()
with tempfile.TemporaryDirectory(prefix='d-meeting-extremes-') as tmp:
 root=Path(tmp);data=root/'data';out=root/'out';data.mkdir();out.mkdir()
 def graph(n):
  with (data/'graph.txt').open('w',buffering=1024*1024) as f:
   f.write(f'{n} {n-1}\n')
   for i in range(n-1):f.write(f'{i} {i+1} 4294967295\n')
 def check(q,expected):
  (data/'queries.txt').write_text(q)
  for b in a.binaries:
   output=out/'distances.txt';output.unlink(missing_ok=True)
   subprocess.run([str(Path(b).resolve())],check=True,env=dict(os.environ,SD_DATA=str(data),SD_OUT=str(out)))
   if output.read_text()!=expected: raise RuntimeError(f'{b}: extreme output mismatch')
 n=1740512;graph(n);check(f'0 {n-1}\n{n-1} 0\n0 0\n',f'{(n-1)*4294967295}\n-1\n0\n');print('PASS max-size max-weight chain, unreachable and self-query',flush=True)
 n=5000;graph(n);check(('0 4999\n4999 0\n')*3000,(f'{4999*4294967295}\n-1\n')*3000);print('PASS 6000 repeated and unreachable queries',flush=True)
