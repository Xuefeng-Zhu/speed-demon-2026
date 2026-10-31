#!/usr/bin/env python3
from pathlib import Path
import subprocess,tempfile
p=Path(__file__).parent
s=(p/'candidate.rs').read_text()+'\n'+(p/'review-tail.rs').read_text()
with tempfile.TemporaryDirectory(prefix='c-prehash-review-') as td:
 t=Path(td);(t/'main.rs').write_text(s)
 subprocess.run(['rustc','--edition=2021','--test','-O','-C','overflow-checks=yes',str(t/'main.rs'),'-o',str(t/'main')],check=True)
 subprocess.run([str(t/'main'),'--nocapture'],check=True,timeout=120)
