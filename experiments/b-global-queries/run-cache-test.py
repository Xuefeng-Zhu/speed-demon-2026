#!/usr/bin/env python3
from pathlib import Path
import platform,subprocess,sys,tempfile
root=Path(__file__).resolve().parents[2];source=(root/'experiments/b-global-queries/shared.rs').read_text();tail=(root/'experiments/b-global-queries/cache-tail.rs').read_text()+'\n'+(root/'experiments/b-global-queries/independent-cache-tail.rs').read_text()
actual='--x86-v3' in sys.argv[1:]
if actual and (platform.system()!='Linux' or platform.machine() not in ('x86_64','amd64')): raise SystemExit('requires Linux x86-64')
flags=['-C','target-cpu=x86-64-v3'] if actual else []
with tempfile.TemporaryDirectory() as d:
 p=Path(d)/'test.rs';exe=Path(d)/'test';p.write_text(source+'\n'+tail)
 subprocess.run(['rustc','--edition=2021','--test','-O','-C','overflow-checks=yes',*flags,str(p),'-o',str(exe)],check=True)
 subprocess.run([str(exe),'--nocapture'],check=True)
