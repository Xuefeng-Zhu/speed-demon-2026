#!/usr/bin/env python3
"""Exercise both pre-output fallback gates against the official reference."""
import argparse
import hashlib
import os
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT=Path(__file__).resolve().parents[2];HERE=Path(__file__).resolve().parent
EXPECTED='d66d963c2388961af0117f40d2938c79df4004eace5a0087b1898af8d66fbd70'
p=argparse.ArgumentParser();p.add_argument('--avx2',action='store_true');a=p.parse_args()
s=(HERE/'candidate.rs').read_text();assert hashlib.sha256(s.encode()).hexdigest()==EXPECTED
worker='let n = thread::available_parallelism().map_or(1, |n| n.get());'
fallback='''    } else {
        let names: Vec<Shard>'''
assert s.count(worker)==1 and s.count(fallback)==1
s=s.replace(fallback,'''    } else {
        eprintln!("FORCED_FALLBACK_BRANCH");
        let names: Vec<Shard>''',1)
variants={
 'file':s.replace('const MAX_PACKED_FILE: usize = u32::MAX as usize;', 'const MAX_PACKED_FILE: usize = 1;',1),
 'group':s.replace('const MAX_PACKED_GROUPS: usize = u16::MAX as usize;', 'const MAX_PACKED_GROUPS: usize = 1;',1),
}
def quote(v):return '"'+v.replace('"','""')+'"'
flags=['-C','target-cpu=x86-64-v3'] if a.avx2 else []
with tempfile.TemporaryDirectory(prefix='c-two-lane-fallback-') as td:
 root=Path(td);data=root/'data';ref=root/'ref';data.mkdir();ref.mkdir()
 (data/'regions.csv').write_bytes(b'region_id,country\n1,AAA\n2,BBB\n')
 rows=[b'\xef\xbb\xbfid,name,note,region_id,amount\r\n']
 for i in range(1,121):
  name=('Long '+('z'*70000)) if i==43 else ['','A, B','Q "quoted"','Name  '][i%4]
  note='alpha\nbeta, "q"';term=b'\r\n' if i%7==0 or i==120 else b'\n'
  bom=b'\xef\xbb\xbf' if i%31==0 else b''
  name_field='' if not name and i%8==0 else quote(name)
  rows.append(bom+f'{i},{name_field},{quote(note)},{1+i%2},-0.05'.encode()+term)
 (data/'records.csv').write_bytes(b''.join(rows))
 subprocess.run([sys.executable,str(ROOT/'official/reference/c_join.py'),'--data',str(data),'--out',str(ref)],check=True,stdout=subprocess.DEVNULL)
 expected=(ref/'aggregates.txt').read_bytes()
 for label,src in variants.items():
  for n in (1,2,3,7,12):
   path=root/f'{label}-{n}.rs';exe=root/f'{label}-{n}';out=root/f'out-{label}-{n}';out.mkdir()
   path.write_text(src.replace(worker,f'let n = {n};'))
   subprocess.run(['rustc','--edition=2021','-O','-C','overflow-checks=yes','-C','debug-assertions=yes',*flags,str(path),'-o',str(exe)],check=True)
   run=subprocess.run([str(exe)],env=dict(os.environ,SD_DATA=str(data),SD_OUT=str(out)),capture_output=True,text=True,check=True)
   assert 'FORCED_FALLBACK_BRANCH' in run.stderr,(label,n,'branch not taken')
   assert (out/'aggregates.txt').read_bytes()==expected,(label,n,'output')
print('PASS both forced pre-output fallbacks across 5 worker counts')
