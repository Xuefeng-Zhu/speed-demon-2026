#!/usr/bin/env python3
"""Force both summary branches and bitmap-cap fallback; compare references."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile

here = Path(__file__).resolve().parent
root = here.parents[1]
source = (here / 'candidate.rs').read_text()
branch = 'if n <= 8 {'
cap = 'let bitmap_limit = 64 * 1024 * 1024 / nthreads;'
assert source.count(branch) == 1 and source.count(cap) == 1
variants = {'dense': source.replace(branch, 'if n <= 0 {'),
            'sparse': source.replace(branch, 'if n <= 64 {'),
            'cap0': source.replace(cap, 'let bitmap_limit = 0 / nthreads;'),
            'cap256': source.replace(cap, 'let bitmap_limit = 256 / nthreads;')}
adapter = str(root / 'experiments/b-rust-positional-adapter.py')
with tempfile.TemporaryDirectory(prefix='b-bitstats-forced-') as temp:
    temp = Path(temp)
    for name, text in variants.items():
        src = temp / (name + '.rs')
        binary = temp / name
        src.write_text(text)
        subprocess.run(['rustc', '--edition=2021', '-C', 'opt-level=2', '-C',
                        'overflow-checks=yes', str(src), '-o', str(binary)], check=True)
        env = dict(os.environ, B_RUST_BINARY=str(binary))
        for fixture in ('experiments/b-bounded-fuzz.py',
                        'experiments/b-frequent-bitmap/tests/dense.py'):
            subprocess.run([sys.executable, str(root / fixture), adapter],
                           cwd=root, env=env, check=True)
print('PASS forced dense, sparse, zero-cap and small-cap reference fixtures')
