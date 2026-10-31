#!/usr/bin/env python3
"""Run independent, hash-pinned EdgeBin tests without altering candidate source."""
import hashlib
import pathlib
import subprocess
import tempfile

root = pathlib.Path(__file__).resolve().parents[2]
src = root / 'experiments/track-d-compact-loader-stream/candidate.rs'
expected = 'd74c9104ddb3ce661e1e597276c2bb9da621a73bbe6846cd82f901de719c1d64'
assert hashlib.sha256(src.read_bytes()).hexdigest() == expected
tail = pathlib.Path(__file__).with_name('tail.rs').read_text()
with tempfile.TemporaryDirectory(prefix='d-loader-independent-') as temp:
    tmp = pathlib.Path(temp)
    source = tmp / 'independent.rs'
    binary = tmp / 'independent'
    source.write_text(src.read_text() + '\n' + tail)
    subprocess.run(['rustc', '--edition=2021', '--test', '-O', '-C', 'overflow-checks=yes',
                    '-C', 'debug-assertions=yes', str(source), '-o', str(binary)], check=True)
    subprocess.run([str(binary)], check=True)
