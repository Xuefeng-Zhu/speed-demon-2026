#!/usr/bin/env python3
"""Check a strong-fallback shard merges correctly with a weak-hash shard."""
import argparse,hashlib,os,subprocess,sys,tempfile
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--binary',required=True,type=Path);p.add_argument('--reference',required=True,type=Path);p.add_argument('--require-restart-marker',action='store_true');a=p.parse_args()
names=[f'/abcdefghijklmno{i:04d}' for i in range(50)]
assert all(len(x)==20 for x in names) and len({x[:16] for x in names})==1
other=[f'/{i:015x}1234' for i in range(99)];assert all(len(x)==20 for x in other)
lines=[f'2026-10-30T18:00:00.000000Z GET {name} 200 0\n' for name in names*2+[names[0]]+other];assert len(lines)==200 and len({len(x) for x in lines})==1
with tempfile.TemporaryDirectory(prefix='a-mixed-shards-') as tmp:
 root=Path(tmp);d=root/'data';o=root/'out';r=root/'ref';d.mkdir();o.mkdir();r.mkdir();(d/'requests.log').write_text(''.join(lines))
 subprocess.run([sys.executable,str(a.reference.resolve()),'--data',str(d),'--out',str(r)],check=True);want=(r/'summary.txt').read_bytes()
 for n in (1,2,3,7,12,32):
  result=subprocess.run([str(a.binary.resolve())],env=dict(os.environ,SD_DATA=str(d),SD_OUT=str(o),SD_THREADS=str(n)),capture_output=True,text=True,check=True)
  assert (o/'summary.txt').read_bytes()==want,n
  if n==2 and a.require_restart_marker:assert result.stderr.count('WEAK_RESTART')==1,result.stderr
 print('PASS mixed shards at 1/2/3/7/12/32 workers; reference SHA256',hashlib.sha256(want).hexdigest())
