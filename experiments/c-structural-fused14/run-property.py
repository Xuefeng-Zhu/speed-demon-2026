#!/usr/bin/env python3
from pathlib import Path
import argparse,subprocess,tempfile
p=argparse.ArgumentParser();p.add_argument('--avx2',action='store_true');a=p.parse_args()
here=Path(__file__).resolve().parent
with tempfile.TemporaryDirectory(prefix='c-structural-property-') as d:
 t=Path(d); src=t/'main.rs';src.write_text((here/'candidate.rs').read_text()+'\n'+(here/'property-tail.rs').read_text())
 flags=['-C','target-cpu=x86-64-v3'] if a.avx2 else []
 subprocess.run(['rustc','--edition=2021','--test','-O','-C','overflow-checks=yes','-C','debug-assertions=yes',*flags,str(src),'-o',str(t/'test')],check=True)
 subprocess.run([str(t/'test')],check=True,timeout=180)
