#!/usr/bin/env python3
"""Reproduce exact owner-cache tests and mixed CSV references, no data bundled."""
from pathlib import Path
import subprocess
import sys
import tempfile

here = Path(__file__).resolve().parent
root = here.parents[1]
with tempfile.TemporaryDirectory(prefix='c-inline-cache-test-') as tmp:
    tmp = Path(tmp)
    for name, tail in [('candidate.rs','test-tail.rs'), ('candidate24.rs','test-tail24.rs')]:
        source = tmp / 'combined.rs'
        binary = tmp / 'test'
        source.write_text((here / name).read_text() + '\n' + (here / tail).read_text())
        subprocess.run(['rustc','--edition=2021','--test','-O','-C','overflow-checks=yes','-C','debug-assertions=yes',str(source),'-o',str(binary)],check=True)
        subprocess.run([str(binary),'--test-threads=1'],check=True)
        subprocess.run([sys.executable,str(root/'experiments/c-rowcache-short-eq/reference.py'),'--source',str(here/name),'--seeds','12'],check=True)
