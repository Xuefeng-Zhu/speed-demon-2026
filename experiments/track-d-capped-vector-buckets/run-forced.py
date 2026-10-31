#!/usr/bin/env python3
from pathlib import Path
import subprocess,tempfile
p=Path(__file__).resolve().parent
src=(p/'candidate.rs').read_text();tail=(p/'forced-tail.rs').read_text()
with tempfile.TemporaryDirectory(prefix='d-vector-forced-') as t:
 t=Path(t)
 for cap in (0,1,2):
  out=t/f'cap{cap}.rs';binary=t/f'cap{cap}'
  assert src.count('const POOL_CAP: usize = 65_536;')==1
  out.write_text(src.replace('const POOL_CAP: usize = 65_536;',f'const POOL_CAP: usize = {cap};')+'\n'+tail)
  subprocess.run(['rustc','--edition=2021','--test','-O','-C','overflow-checks=yes','-C','debug-assertions=yes',str(out),'-o',str(binary)],check=True)
  subprocess.run([str(binary)],check=True)
