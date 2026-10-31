#!/usr/bin/env python3
"""Validate shared narrow/wide ownership, output and cleanup; temporary builds only."""
import argparse
import hashlib
from pathlib import Path
import subprocess
import tempfile

p = argparse.ArgumentParser()
p.add_argument('--cpu')
p.add_argument('--extremes', action='store_true')
a = p.parse_args()
here = Path(__file__).resolve().parent
root = here.parents[1]
src = (here / 'candidate.rs').read_text()
expected = '44513bbf5201b2d47986ab947ff793a35ff7e430b49ea1e6dc0453e9211241c9'
assert hashlib.sha256(src.encode()).hexdigest() == expected
marker = 'const POOL_CAP: usize = 65_536;'
assert src.count(marker) == 1
tail = (here / 'transition-tail.rs').read_text()

def run(*args):
    subprocess.run([str(x) for x in args], check=True)

flags = ['rustc', '--edition=2021', '-O', '-C', 'overflow-checks=yes',
         '-C', 'debug-assertions=yes']
if a.cpu:
    flags += ['-C', f'target-cpu={a.cpu}']
with tempfile.TemporaryDirectory(prefix='d-shared-state-') as tmp:
    tmp = Path(tmp)
    bins = []
    for cap in (0, 1, 2, 65536):
        body = src.replace(marker, f'const POOL_CAP: usize = {cap};')
        path, binary = tmp / f'cap{cap}.rs', tmp / f'cap{cap}'
        path.write_text(body)
        run(*flags, path, '-o', binary)
        bins.append(binary)
        test_src, test_bin = tmp / f'test{cap}.rs', tmp / f'test{cap}'
        test_src.write_text(body + '\n' + tail)
        run(*flags, '--test', test_src, '-o', test_bin)
        run(test_bin)
    for script in ('oracle.py', 'exhaustive.py'):
        run('python3', root / 'experiments/track-d-balanced-frontier' / script, *bins)
    run('python3', root / 'experiments/track-d-u32-fallback/thresholds.py', *bins)
    for binary in (bins[1], bins[3]):
        run('python3', root / 'experiments/track-d-packed32-adj/boundaries.py', binary)
    if a.extremes:
        run('python3', root / 'experiments/track-d-balanced-frontier/extremes.py', bins[1], bins[3])
print('PASS shared-state transitions, cleanup, references and forced capacities')
