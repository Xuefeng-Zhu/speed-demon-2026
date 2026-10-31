#!/usr/bin/env python3
"""Test the actual default-capacity candidate with a cached-minimum auditor."""
from pathlib import Path
import hashlib, subprocess, tempfile
p = Path(__file__).resolve().parent
s = (p / 'candidate.rs').read_text()
assert hashlib.sha256(s.encode()).hexdigest() == '628b0922b43babe854af632876ce43a328c3d5b82286157aa6d7b1bf5b8c81ef'
with tempfile.TemporaryDirectory(prefix='sd-min-boundary-') as td:
    t = Path(td); source = t / 'test.rs'; binary = t / 'test'
    source.write_text(s + '\n' + (p / 'pool-boundary-tail.rs').read_text() + '\n' + (p / 'min-audit-tail.rs').read_text())
    subprocess.run(['rustc','--edition=2021','--test','-O','-C','overflow-checks=yes','-C','debug-assertions=yes',str(source),'-o',str(binary)],check=True)
    subprocess.run([str(binary)],check=True)
