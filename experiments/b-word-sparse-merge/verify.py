#!/usr/bin/env python3
"""Verify exact-source sparse word merges, forced paths and word boundaries."""
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
source = (HERE / 'candidate.rs').read_text()
needle = 'if sparse_cost <= SPARSE_WORD_BUDGET {'
workers = 'let nthreads = thread::available_parallelism().map_or(4, |n| n.get());'
assert source.count(needle) == source.count(workers) == 1

with tempfile.TemporaryDirectory(prefix='sd-b-word-sparse-') as tmp:
    tmp = Path(tmp)
    binaries = {}
    for name, condition in [('auto', needle), ('always', 'if true {'), ('never', 'if false {')]:
        text = source.replace(needle, condition).replace(workers, 'let nthreads = 1;')
        if condition != needle:
            text = text.replace('const SPARSE_WORD_BUDGET: usize = 512;', '#[allow(dead_code)] const SPARSE_WORD_BUDGET: usize = 512;')
        src, exe = tmp / (name + '.rs'), tmp / name
        src.write_text(text)
        subprocess.run(['rustc', '--edition=2021', '-O', '-C', 'overflow-checks=yes', '-C', 'debug-assertions=yes', str(src), '-o', str(exe)], check=True)
        binaries[name] = str(exe)
    subprocess.run([sys.executable, str(ROOT / 'experiments/b-sparse-postings/cutoff-review.py'), binaries['never'], binaries['auto']], cwd=ROOT, check=True)
    for name in ('auto', 'always'):
        binary = binaries[name]
        env = dict(os.environ, B_RUST_BINARY=binary)
        if name == 'always':
            subprocess.run([sys.executable, str(ROOT / 'experiments/b-boolean-clauses/algebra.py'), str(ROOT / 'experiments/b-rust-positional-adapter.py')], cwd=ROOT, env=env, check=True)
        subprocess.run([sys.executable, str(ROOT / 'experiments/b-bounded-fuzz.py'), str(ROOT / 'experiments/b-rust-positional-adapter.py')], cwd=ROOT, env=env, check=True)
        print('PASS', name, flush=True)
