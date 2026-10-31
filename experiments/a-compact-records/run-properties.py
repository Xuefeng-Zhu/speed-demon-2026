#!/usr/bin/env python3
from pathlib import Path
import platform, subprocess, tempfile
root=Path(__file__).resolve().parents[2]
s=(root/'experiments/a-compact-records/candidate.rs').read_text()
if platform.system()=='Darwin':
 a='let (read, private, fixed, anon, null) = (1, 2, 0x10, 0x20, std::ptr::null_mut());'
 assert s.count(a)==1;s=s.replace(a,'let (read, private, fixed, anon, null) = (1, 2, 0x10, 0x1000, std::ptr::null_mut());')
s+='\n'+(root/'experiments/a-compact-records/record-tail.rs').read_text()
with tempfile.TemporaryDirectory() as d:
 p=Path(d)/'test.rs';binary=Path(d)/'test';p.write_text(s)
 # Baseline SWAR arithmetic intentionally wraps, so match release overflow mode.
 subprocess.run(['rustc','--edition=2021','--test','-O','-C','overflow-checks=off',str(p),'-o',str(binary)],check=True)
 subprocess.run([str(binary),'--nocapture'],check=True)
