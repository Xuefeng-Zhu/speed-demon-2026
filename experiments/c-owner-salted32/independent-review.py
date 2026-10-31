#!/usr/bin/env python3
from pathlib import Path
import subprocess,tempfile
p=Path(__file__).parent
s=(p/'candidate.rs').read_text()+'\n'+(p/'review-tail.rs').read_text()
with tempfile.TemporaryDirectory(prefix='c-salted32-independent-') as td:
 t=Path(td);src=t/'main.rs';src.write_text(s)
 subprocess.run(['rustc','--edition=2021','--test','-O','-C','overflow-checks=yes',str(src),'-o',str(t/'test')],check=True)
 subprocess.run([str(t/'test'),'--nocapture'],check=True,timeout=120)
