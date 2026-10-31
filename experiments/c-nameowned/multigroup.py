#!/usr/bin/env python3
import os,sys,tempfile,subprocess,random
from pathlib import Path
src=Path(sys.argv[1]).resolve(); reference=Path(sys.argv[2]).resolve()
s=src.read_text(); needle='let n = thread::available_parallelism().map_or(1, |n| n.get());'; assert s.count(needle)==1
with tempfile.TemporaryDirectory(prefix='c-multigroup-') as d:
 p=Path(d);data=p/'data';ref=p/'ref';data.mkdir();ref.mkdir()
 (data/'regions.csv').write_text('region_id,country\n'+''.join(f'{i+1},C{i:03d}\n' for i in range(240)))
 rng=random.Random(90210);rows=[]
 for i in range(240*17):
  g=i%240+1; name=['same','same ','long '+str(i%23),'quote " x',''][i%5]
  note=['has\nline','comma, quote "',''][i%3]
  q=lambda x:'"'+x.replace('"','""')+'"'
  rows.append(f'{i+1},{q(name)},{q(note)},{g},{rng.randrange(-999,1000)/100:.2f}'+ ('\r\n' if i%3==0 or i==240*17-1 else '\n'))
 (data/'records.csv').write_bytes(('\ufeffid,name,note,region_id,amount\r\n'+''.join(rows)).encode())
 subprocess.run([sys.executable,str(reference),'--data',str(data),'--out',str(ref)],check=True)
 expected=(ref/'aggregates.txt').read_bytes()
 for n in (1,2,3,7,12,32):
  for force in (False,True):
   z=s.replace(needle,f'let n = {n};'); z=z.replace('        self.0 ^ self.0 >> 29\n','        0\n') if force else z
   tmp=p/f'c{n}-{force}.rs';tmp.write_text(z);exe=p/f'c{n}-{force}';subprocess.run(['rustc','--edition=2021','-O',str(tmp),'-o',str(exe)],check=True)
   out=p/f'out{n}-{force}';out.mkdir();subprocess.run([str(exe)],env=dict(os.environ,SD_DATA=str(data),SD_OUT=str(out)),check=True)
   assert (out/'aggregates.txt').read_bytes()==expected,(n,force)
print('PASS: 240 groups, names shared across groups, six workers, normal/forced-collision hashes')
