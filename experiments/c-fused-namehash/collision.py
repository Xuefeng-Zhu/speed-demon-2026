#!/usr/bin/env python3
"""Test distinct owner/hash collision handling under duplicate traffic and growth."""
import os,subprocess,sys,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];HERE=Path(__file__).parent
s=(HERE/'candidate.rs').read_text()
needle='let n = thread::available_parallelism().map_or(1, |n| n.get());'
route='let (name, name_len, h) = field_name_hash(recs, &mut p);'
finish='self.0 ^ self.0 >> 29'
for x in (needle,route,finish):assert s.count(x)==1
s=s.replace(needle,'let n = std::env::var("SD_TEST_WORKERS").unwrap().parse::<usize>().unwrap();')
variants={'normal':s,'owner_collision':s.replace(route,'let (name, name_len, _h) = field_name_hash(recs, &mut p); let h = 0u64;'),'fullhash_collision':s.replace(finish,'0').replace(route,'let (name, name_len, _h) = field_name_hash(recs, &mut p); let h = 0u64;')}
flags=['-C','target-cpu=x86-64-v3'] if '--avx2' in sys.argv else []
with tempfile.TemporaryDirectory(prefix='c-compact-collision-') as td:
 root=Path(td);data=root/'data';ref=root/'ref';data.mkdir();ref.mkdir();bins={}
 for label,body in variants.items():
  src=root/f'{label}.rs';exe=root/label;src.write_text(body)
  subprocess.run(['rustc','--edition=2021','-O','-C','overflow-checks=yes']+flags+[str(src),'-o',str(exe)],check=True);bins[label]=exe
 (data/'regions.csv').write_text('region_id,country\n'+''.join(f'{i+1},AA{chr(65+i)}\n' for i in range(8)))
 rows=[b'\xef\xbb\xbfid,name,note,region_id,amount\r\n']
 for i in range(1,12_001):
  name=f'Collision name {i%2000:04d}'+(' ' if i%7==0 else '')
  rows.append(f'{i},"{name}","note",{1+i%8},{"-0.05" if i%9==0 else "1.25"}\r\n'.encode())
 (data/'records.csv').write_bytes(b''.join(rows))
 subprocess.run([sys.executable,str(ROOT/'official/reference/c_join.py'),'--data',str(data),'--out',str(ref)],check=True,stdout=subprocess.DEVNULL)
 expected=(ref/'aggregates.txt').read_bytes();count=0
 for label,exe in bins.items():
  for workers in (1,2,7,32):
   out=root/f'out-{label}-{workers}';out.mkdir();env=dict(os.environ,SD_DATA=str(data),SD_OUT=str(out),SD_TEST_WORKERS=str(workers))
   subprocess.run([str(exe)],env=env,check=True,timeout=90,stdout=subprocess.DEVNULL)
   assert (out/'aggregates.txt').read_bytes()==expected,(label,workers);count+=1
 print(f'PASS {count} owner/full-hash collision, growth and repeated-name reference checks')
