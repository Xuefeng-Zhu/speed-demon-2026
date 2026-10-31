#!/usr/bin/env python3
"""Validate exact cached-bit writeback and fallback against a HashSet oracle."""
from pathlib import Path
import subprocess
import tempfile
here = Path(__file__).resolve().parent
with tempfile.TemporaryDirectory(prefix='c-writeback-prop-') as d:
    source = Path(d) / 'test.rs'
    binary = Path(d) / 'test'
    source.write_bytes((here / 'candidate.rs').read_bytes() + b'\n' + (here / 'property-tail.rs').read_bytes())
    subprocess.run(['rustc', '--edition=2021', '--test', '-O', '-C', 'overflow-checks=yes', '-C', 'debug-assertions=yes', str(source), '-o', str(binary)], check=True)
    subprocess.run([str(binary), '--nocapture'], check=True)
