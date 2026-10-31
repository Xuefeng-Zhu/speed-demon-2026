#!/usr/bin/env python3
from pathlib import Path
import subprocess,tempfile
p=Path(__file__).parent
s=(p/'candidate.rs').read_text()+(p/'independent-adversarial-tail.rs').read_text()
with tempfile.TemporaryDirectory(prefix='c-swar-adversarial-') as t:
    t=Path(t);(t/'main.rs').write_text(s)
    subprocess.run(['rustc','--edition=2021','--test','-O','-C','overflow-checks=yes',str(t/'main.rs'),'-o',str(t/'main')],check=True)
    subprocess.run([str(t/'main')],check=True)
