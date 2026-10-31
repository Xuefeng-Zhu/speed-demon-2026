#!/usr/bin/env python3
"""Country-code domain and sparse sorted region edge comparisons."""
import os,subprocess,sys,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]; HERE=Path(__file__).parent
s=(HERE/'combined.rs').read_text();needle='let n = thread::available_parallelism().map_or(1, |n| n.get());';assert s.count(needle)==1
s=s.replace(needle,'let n = std::env::var("SD_TEST_WORKERS").unwrap().parse::<usize>().unwrap();')
with tempfile.TemporaryDirectory(prefix='c-lookup-boundaries-') as tmp:
 p=Path(tmp);src=p/'main.rs';exe=p/'main';src.write_text(s);subprocess.run(['rustc','--edition=2021','-O','-C','overflow-checks=yes',str(src),'-o',str(exe)],check=True)
 total=0
 for count in (0,1,240,513,17576):
  d=p/f'data{count}';o=p/f'out{count}';r=p/f'ref{count}';d.mkdir();o.mkdir();r.mkdir()
  codes=[chr(65+i//676)+chr(65+(i//26)%26)+chr(65+i%26) for i in range(count)]
  ids=([1+i*2 for i in range(count-1)]+[999999]) if count else []
  (d/'regions.csv').write_text('region_id,country\n'+''.join(f'{v},{code}\n' for v,code in zip(ids,codes)))
  lines=[b'\xef\xbb\xbfid,name,note,region_id,amount\r\n']
  for i,v in enumerate(ids,1):lines.append(f'{i},"Name-{i%37}","hello",{v},{"-0.05" if i%2 else "1.00"}\r\n'.encode())
  lines.append(f'{len(ids)+1},"missing","x",9999999,0.00\r\n'.encode())
  (d/'records.csv').write_bytes(b''.join(lines))
  subprocess.run([sys.executable,str(ROOT/'official/reference/c_join.py'),'--data',str(d),'--out',str(r)],check=True,stdout=subprocess.DEVNULL)
  expected=(r/'aggregates.txt').read_bytes()
  for workers in (1,2,7,32):
   out=o/'aggregates.txt';out.unlink(missing_ok=True)
   env=dict(os.environ,SD_DATA=str(d),SD_OUT=str(o),SD_TEST_WORKERS=str(workers))
   subprocess.run([str(exe)],env=env,check=True,timeout=90,stdout=subprocess.DEVNULL)
   assert out.read_bytes()==expected,(count,workers)
   total+=1
 print(f'PASS {total} lookup edge/reference comparisons (0,1,240,513,17576 countries; sparse max id 999999)')
