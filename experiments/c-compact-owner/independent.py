#!/usr/bin/env python3
from pathlib import Path
import subprocess,sys,tempfile
p=Path(__file__).parent
s=(p/'candidate.rs').read_text()+(p/'review-tail.rs').read_text()
with tempfile.TemporaryDirectory(prefix='c-compact-review-') as tmp:
 t=Path(tmp);src=t/'main.rs';src.write_text(s)
 subprocess.run(['rustc','--edition=2021','--test','-O','-C','overflow-checks=yes'] + (['-C','target-cpu=x86-64-v3'] if '--avx2' in sys.argv else []) + [str(src),'-o',str(t/'main')],check=True)
 subprocess.run([str(t/'main')],check=True,timeout=60)
