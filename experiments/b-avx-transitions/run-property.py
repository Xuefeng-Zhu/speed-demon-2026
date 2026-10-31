#!/usr/bin/env python3
from pathlib import Path
import platform, subprocess, sys, tempfile
root=Path(__file__).resolve().parents[2]
source=(root/'experiments/b-avx-transitions/candidate.rs').read_text()
tail=(root/'experiments/b-avx-transitions/token-tail.rs').read_text()
actual='--x86-v3' in sys.argv[1:]
if actual and (platform.system()!='Linux' or platform.machine() not in ('x86_64','amd64')):
    raise SystemExit('--x86-v3 requires Linux x86-64')
flags=['-C','target-cpu=x86-64-v3'] if actual else []
with tempfile.TemporaryDirectory() as tmp:
 p=Path(tmp)/'property.rs';binary=Path(tmp)/'property';p.write_text(source+'\n'+tail)
 subprocess.run(['rustc','--edition=2021','--test','-O','-C','overflow-checks=yes',*flags,str(p),'-o',str(binary)],check=True)
 result=subprocess.run([str(binary),'--nocapture'],check=True,text=True,capture_output=True)
 print(result.stdout)
 if actual and 'independent_transition::actual_avx2_enabled ... ok' not in result.stdout:
    raise SystemExit('actual AVX2 test did not run')
