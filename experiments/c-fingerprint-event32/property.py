#!/usr/bin/env python3
"""Compile exact source plus overflow-checked fingerprint oracle tests."""
from pathlib import Path
import subprocess,sys,tempfile
p=Path(__file__).resolve().parent
source=(p/'candidate.rs').read_text()+'\n'+(p/'property-tail.rs').read_text()
flags=['-C','target-cpu=x86-64-v3'] if '--avx2' in sys.argv else []
with tempfile.TemporaryDirectory(prefix='c-fingerprint-property-') as td:
 root=Path(td);(root/'source.rs').write_text(source)
 subprocess.run(['rustc','--edition=2021','--test','-O','-C','overflow-checks=yes','-C','debug-assertions=yes',*flags,str(root/'source.rs'),'-o',str(root/'test')],check=True)
 subprocess.run([str(root/'test'),'--test-threads=1'],check=True,timeout=120)
