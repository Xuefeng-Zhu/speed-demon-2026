#!/usr/bin/env python3
"""Generate a temporary skewed graph; assert actual cap fallback and exact answers."""
from pathlib import Path
import argparse, hashlib, os, subprocess, tempfile
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--edges',type=int,default=10000)
p.add_argument('--nodes',type=int,default=3)
p.add_argument('--threads',type=int,default=12)
p.add_argument('--timeout',type=int,default=180)
p.add_argument('--cpu')
a=p.parse_args()
if not (2<=a.edges<=5000000 and 3<=a.nodes<=1740512 and 1<=a.threads<=12 and a.timeout>0):p.error('invalid dimensions')
here=Path(__file__).resolve().parent
s=(here/'candidate.rs').read_text()
assert hashlib.sha256(s.encode()).hexdigest()=='77f764359aa3189f73e37d2b411ba80a700ee66ee25a40c0286e658ab45f52d4'
s=s.replace('Some(graphs) => graphs,','Some(graphs) => { eprintln!("GUARD_FAST"); graphs },',1)
s=s.replace('None => load_graph_exact(path, threads),','None => { eprintln!("GUARD_FALLBACK"); load_graph_exact(path, threads) },',1)
needle='let threads = thread::available_parallelism().map_or(1, |n| n.get()).min(12);'
assert s.count(needle)==1
s=s.replace(needle,f'let threads = {a.threads}usize;',1)
with tempfile.TemporaryDirectory(prefix='d-guard-skew-') as tmp:
 t=Path(tmp);data=t/'data';out=t/'out';data.mkdir();out.mkdir()
 with (data/'graph.txt').open('w',encoding='ascii') as f:
  f.write(f'{a.nodes} {a.edges}\n')
  chunk='0 1 1\n'*10000
  blocks,rem=divmod(a.edges-1,10000)
  for _ in range(blocks):f.write(chunk)
  f.write('0 1 1\n'*rem);f.write('1 2 1\n')
 (data/'queries.txt').write_text('0 2\n2 0\n0 0\n',encoding='ascii')
 src=t/'test.rs';binary=t/'test';src.write_text(s)
 flags=['rustc','--edition=2021','-O','-C','overflow-checks=yes','-C','debug-assertions=yes']
 if a.cpu:flags+=['-C','target-cpu='+a.cpu]
 subprocess.run([*flags,str(src),'-o',str(binary)],check=True)
 r=subprocess.run([str(binary)],env={**os.environ,'SD_DATA':str(data),'SD_OUT':str(out)},text=True,capture_output=True,timeout=a.timeout,check=True)
 if 'GUARD_FALLBACK' not in r.stderr:raise SystemExit('FAIL skew fixture did not trigger actual fallback')
 if (out/'distances.txt').read_text()!='2\n-1\n0\n':raise SystemExit('FAIL wrong answers')
 print(f'PASS actual fallback and exact answers: nodes={a.nodes} edges={a.edges} threads={a.threads}')
