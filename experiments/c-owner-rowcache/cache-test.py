#!/usr/bin/env python3
from pathlib import Path
import subprocess,sys,tempfile
p=Path(__file__).parent
s=(p/'candidate.rs').read_text()+'\n'+(p/'cache-tail.rs').read_text()
with tempfile.TemporaryDirectory(prefix='c-rowcache-test-') as d:
 t=Path(d);src=t/'main.rs';src.write_text(s)
 flags=['-C','target-cpu=x86-64-v3'] if '--avx2' in sys.argv else []
 subprocess.run(['rustc','--edition=2021','--test','-O','-C','overflow-checks=yes']+flags+[str(src),'-o',str(t/'main')],check=True)
 subprocess.run([str(t/'main')],check=True,timeout=90)
