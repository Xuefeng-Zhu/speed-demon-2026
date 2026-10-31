#!/usr/bin/env python3
"""Actual Linux/x86 guarded-page prefetch test; no effect on selected source."""
from pathlib import Path
import os,subprocess,tempfile,sys
if sys.platform != 'linux' or os.uname().machine != 'x86_64':
    raise SystemExit('requires actual Linux x86_64; no portability substitution')
p=Path(__file__).resolve().parent
with tempfile.TemporaryDirectory(prefix='c-dep-prefetch-guard-') as d:
    source=Path(d)/'test.rs'; source.write_text((p/'candidate.rs').read_text()+'\n'+(p/'guard-tail.rs').read_text())
    binary=Path(d)/'test'; subprocess.run(['rustc','--edition=2021','--test','-O','-C','overflow-checks=yes',str(source),'-o',str(binary)],check=True)
    subprocess.run([str(binary)],check=True,timeout=60)
