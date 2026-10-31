#!/usr/bin/env python3
from pathlib import Path
import subprocess,tempfile
p=Path(__file__).parent;s=(p/'candidate.rs').read_text()+(p/'independent-heads-tail.rs').read_text()
with tempfile.TemporaryDirectory(prefix='c-headmap-review-') as tmp:
 t=Path(tmp);src=t/'main.rs';src.write_text(s)
 subprocess.run(['rustc','--edition=2021','--test','-O','-C','overflow-checks=yes',str(src),'-o',str(t/'main')],check=True)
 subprocess.run([str(t/'main')],check=True,timeout=90)
