#!/usr/bin/env python3
"""Forced-fallback and collision checks; execute from repository or archive root."""
import os
import subprocess
import tempfile
from pathlib import Path
root = Path(__file__).resolve().parents[2]
dir = root / 'experiments/b-displaced-short25'
source = (dir / 'candidate.rs').read_text()
tail = (dir / 'property-tail.rs').read_text()
compiler = ['rustc', '--edition=2021', '-C', 'opt-level=2', '-C', 'overflow-checks=yes']
with tempfile.TemporaryDirectory(prefix='b-displaced-verify-') as temp:
    tmp = Path(temp)
    test_source = tmp / 'property.rs'
    test_source.write_text(source + '\n' + tail)
    subprocess.run(compiler + ['--test', str(test_source), '-o', str(tmp / 'property')], check=True)
    subprocess.run([str(tmp / 'property')], check=True)
    budget_old = 'let mut budget = count.saturating_mul(64).min(4_000_000);'
    assert source.count(budget_old) == 1
    variants = {'budget-zero': source.replace(budget_old, 'let mut budget = 0usize;')}
    start = source.index('    fn short_hash64(mut x: u64) -> u64 {')
    end = source.index('\n    #[inline]\n    fn short_hash(', start)
    variants['constant-hash'] = source[:start] + '    fn short_hash64(_x: u64) -> u64 { 0 }\n' + source[end:]
    for name, text in variants.items():
        src, binary = tmp / (name + '.rs'), tmp / name
        src.write_text(text)
        subprocess.run(compiler + [str(src), '-o', str(binary)], check=True)
        env = dict(os.environ, B_RUST_BINARY=str(binary))
        subprocess.run(['python3', str(root / 'experiments/b-bounded-fuzz.py'), str(root / 'experiments/b-rust-positional-adapter.py')], env=env, check=True)
print('PASS all forced budget/collision and construction-property checks')
