#!/usr/bin/env python3
import os,sys,random,subprocess,tempfile
from pathlib import Path
root=Path(__file__).resolve().parents[2]
src=(root/'experiments/c-nameowned/candidate.rs').read_text()
needle='let n = thread::available_parallelism().map_or(1, |n| n.get());'
assert src.count(needle)==1
reference=root/'official/reference/c_join.py'
with tempfile.TemporaryDirectory(prefix='c-nameowner-review-') as td:
 t=Path(td);d=t/'data';ref=t/'ref';d.mkdir();ref.mkdir()
 codes=[f'{chr(65+i//676)}{chr(65+(i//26)%26)}{chr(65+i%26)}' for i in range(130)]
 (d/'regions.csv').write_text('region_id,country\n'+''.join(f'{i+1},{code}\n' for i,code in enumerate(codes)))
 rng=random.Random(8675309)
 with (d/'records.csv').open('wb') as f:
  f.write(b'\xef\xbb\xbfid,name,note,region_id,amount\r\n')
  for i in range(30000):
   name=('', 'Alice', 'Alice ', 'A, B', 'N "Nick"', 'n'*130, 'shared')[i%7]
   note=('', 'alpha\nbeta', 'said "no"', 'long note')[i%4]
   quote=lambda x:'"'+x.replace('"','""')+'"'
   rid=(i%131)+1; amount=('-0.01' if i%3==0 else ('99999.99' if i%3==1 else '0.00'))
   bom=b'\xef\xbb\xbf' if i and i%173==0 else b''
   end=b'\r\n' if i%2==0 or i==29999 else b'\n'
   f.write(bom+f'{i+1},{quote(name)},{quote(note)},{rid},{amount}'.encode()+end)
 subprocess.run([sys.executable,str(reference),'--data',str(d),'--out',str(ref)],check=True)
 expected=(ref/'aggregates.txt').read_bytes()
 for force in (False,True):
  s=src.replace('        self.0 ^ self.0 >> 29\n','        0\n') if force else src
  for n in (1,2,7,16):
   source=t/f'src-{force}-{n}.rs';source.write_text(s.replace(needle,f'let n = {n};'))
   binary=t/f'bin-{force}-{n}'
   subprocess.run(['rustc','--edition=2021','-O','-C','overflow-checks=yes','-A','dead_code',str(source),'-o',str(binary)],check=True)
   out=t/f'out-{force}-{n}';out.mkdir()
   subprocess.run([str(binary)],env=dict(os.environ,SD_DATA=str(d),SD_OUT=str(out)),check=True)
   actual=(out/'aggregates.txt').read_bytes()
   if actual!=expected:raise AssertionError((force,n))
   print('PASS',force,n,flush=True)
print('PASS all groups/word boundaries and exact collision checks')
