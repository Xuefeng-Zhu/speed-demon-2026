#!/usr/bin/env python3
"""Independently exercise the frozen short-name equality candidate."""
from pathlib import Path
import hashlib
import subprocess
import tempfile

here = Path(__file__).resolve().parent
candidate = here.parent / 'c-rowcache-short-eq' / 'candidate.rs'
expected = '8ab8977bb9956a686792769eb6cd758726538b8dcac4f4336b74539fba23104c'
assert hashlib.sha256(candidate.read_bytes()).hexdigest() == expected
with tempfile.TemporaryDirectory(prefix='sd-independent-row-eq-') as tmp:
    source = Path(tmp) / 'combined.rs'
    binary = Path(tmp) / 'test'
    source.write_text(candidate.read_text() + '\n' + (here / 'test-tail.rs').read_text())
    subprocess.run(['rustc', '--edition=2021', '--test', '-O', '-C', 'overflow-checks=yes', '-C', 'debug-assertions=yes', str(source), '-o', str(binary)], check=True)
    subprocess.run([str(binary), '--test-threads=1'], check=True)
