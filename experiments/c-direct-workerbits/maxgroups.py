#!/usr/bin/env python3
"""Stress all country codes with distinct names and report native RSS, not cgroup."""
from pathlib import Path
import os,subprocess,tempfile
root=Path(__file__).resolve().parents[2];here=Path(__file__).parent
needle='let n = thread::available_parallelism().map_or(1, |n| n.get());'
def code(i): return ''.join(chr(65+(i//k)%26) for k in (676,26,1))
with tempfile.TemporaryDirectory(prefix='c-maxgroups-') as td:
 p=Path(td); data=p/'data';out=p/'out';ref=p/'ref';data.mkdir();out.mkdir();ref.mkdir()
 n=26**3
 (data/'regions.csv').write_text('region_id,country\n'+''.join(f'{i+1},{code(i)}\n' for i in range(n)))
 with (data/'records.csv').open('wb') as f:
  f.write(b'\xef\xbb\xbfid,name,note,region_id,amount\r\n')
  for i in range(n): f.write(f'{i+1},"Name {code(i)}","note",{i+1},1.00\r\n'.encode())
 subprocess.run(['python3',str(root/'official/reference/c_join.py'),'--data',str(data),'--out',str(ref)],check=True,stdout=subprocess.DEVNULL,timeout=90)
 expected=(ref/'aggregates.txt').read_bytes()
 for label in ('baseline','candidate'):
  s=(here/f'{label}.rs').read_text();assert s.count(needle)==1
  src=p/f'{label}.rs';exe=p/label;src.write_text(s.replace(needle,'let n = 32;'))
  subprocess.run(['rustc','--edition=2021','-O','-C','overflow-checks=yes',str(src),'-o',str(exe)],check=True)
  (out/'aggregates.txt').unlink(missing_ok=True)
  process=subprocess.Popen([str(exe)],env=dict(os.environ,SD_DATA=str(data),SD_OUT=str(out)))
  _,status,usage=os.wait4(process.pid,0);process.returncode=os.waitstatus_to_exitcode(status)
  assert process.returncode==0 and (out/'aggregates.txt').read_bytes()==expected
  print(f'{label}: {n} groups, {n} distinct names, 32 workers, native maxrss={usage.ru_maxrss}')
