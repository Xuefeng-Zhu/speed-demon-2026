#!/usr/bin/env python3
"""Long zero cycles in one bucket with intentionally exhausted small pools."""
import os,subprocess,tempfile
from pathlib import Path
src=(Path(__file__).resolve().parent/'shift5.rs').read_text()
marker='Err(())=>{exhausted=true;break \'search;},'
assert src.count(marker)==1
src=src.replace(marker,'Err(())=>{eprintln!("COARSE_SHIFT5_EXHAUSTED");exhausted=true;break \'search;},')
with tempfile.TemporaryDirectory(prefix='coarse-long-') as tmp:
 p=Path(tmp);data=p/'data';out=p/'out';data.mkdir();out.mkdir();n=8193;edges=[]
 for i in range(8190):
  edges.extend(((i,i+1,0),(i+1,i,0)))
  if i+2<8191:edges.append((i,i+2,0))
 for i in range(1,8191):edges.append((0,i,31))
 q=[(0,8190),(8190,0),(300,8000),(8192,0),(0,8192),(8192,8192),(1000,2000)]
 (data/'graph.txt').write_text(f'{n} {len(edges)}\n'+''.join(f'{u} {v} {w}\n' for u,v,w in edges))
 (data/'queries.txt').write_text(''.join(f'{u} {v}\n' for u,v in q));expect=b'0\n0\n0\n-1\n-1\n0\n0\n'
 for cap in (2,16,65536):
  s=p/f'cap{cap}.rs';b=p/f'cap{cap}';s.write_text(src.replace('const POOL_CAP: usize = 65_536;',f'const POOL_CAP: usize = {cap};'))
  subprocess.run(['rustc','--edition=2021','-O','-C','overflow-checks=yes','-C','debug-assertions=yes',str(s),'-o',str(b)],check=True)
  r=subprocess.run([str(b)],check=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,env=dict(os.environ,SD_DATA=str(data),SD_OUT=str(out)))
  assert (out/'distances.txt').read_bytes()==expect,cap
  if cap in (2,16):assert b'COARSE_SHIFT5_EXHAUSTED' in r.stderr,cap
 print('PASS 8191-node same-bucket zero-cycle graph; forced-cap 2/16 exhausted and fallback matched')
