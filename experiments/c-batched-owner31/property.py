#!/usr/bin/env python3
from pathlib import Path
import subprocess,tempfile
root=Path(__file__).resolve().parents[2]
src=(root/'experiments/c-batched-owner31/candidate.rs').read_text()
tail=(root/'experiments/c-batched-owner31/property-tail.rs').read_text()
with tempfile.TemporaryDirectory(prefix='c-batch-prop-') as d:
 p=Path(d); (p/'test.rs').write_text(src+'\n'+tail)
 subprocess.run(['rustc','--edition=2021','--test','-O','-C','overflow-checks=yes','-C','debug-assertions=yes',str(p/'test.rs'),'-o',str(p/'test')],check=True)
 subprocess.run([str(p/'test'),'--nocapture'],check=True)
