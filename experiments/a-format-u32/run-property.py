#!/usr/bin/env python3
from pathlib import Path
import platform, subprocess, tempfile
root=Path(__file__).resolve().parents[2]
s=(root/'experiments/a-format-u32/candidate.rs').read_text()
if platform.system()=='Darwin':
 a='(1, 2, 0x10, 0x20, std::ptr::null_mut())';assert s.count(a)==1;s=s.replace(a,'(1, 2, 0x10, 0x1000, std::ptr::null_mut())')
s+='\n'+(root/'experiments/a-format-u32/property-tail.rs').read_text()
with tempfile.TemporaryDirectory() as d:
 p=Path(d)/'test.rs';out=Path(d)/'test';p.write_text(s)
 subprocess.run(['rustc','--edition=2021','--test','-O','-C','overflow-checks=yes',str(p),'-o',str(out)],check=True)
 subprocess.run([str(out),'--nocapture'],check=True)
