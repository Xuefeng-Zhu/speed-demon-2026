#!/usr/bin/env python3
"""Compile the frozen candidate with independent tests, without changing source."""
import hashlib
import re
import subprocess
import tempfile
from pathlib import Path

here = Path(__file__).resolve().parent
candidate = here.parent / 'b-direct-byte2-current' / 'candidate.rs'
source = candidate.read_text()
assert hashlib.sha256(source.encode()).hexdigest() == 'a2691fb564324be0fd4427adad67561d6374be6a27a3d83674343fd29eaaa727'
tail = (here / 'test-tail.rs').read_text()
with tempfile.TemporaryDirectory(prefix='b-byte2-independent-') as td:
    root = Path(td)
    for mode in ('normal', 'forced-collision'):
        text = source
        if mode == 'forced-collision':
            text, n = re.subn(r'fn short_hash\(mut x: u64\) -> usize \{.*?\n    \}',
                              'fn short_hash(_x: u64) -> usize { 0\n    }', text, count=1, flags=re.S)
            assert n == 1
        path = root / (mode + '.rs')
        binary = root / mode
        path.write_text(text + '\n' + tail)
        subprocess.run(['rustc', '--edition=2021', '--test', '-O', '-C', 'overflow-checks=yes',
                        '-C', 'debug-assertions=yes', str(path), '-o', str(binary)], check=True)
        subprocess.run([str(binary)], check=True)
