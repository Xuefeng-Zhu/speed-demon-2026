#!/usr/bin/env python3
"""Compile and run independent loader properties and exact graph oracles."""
import argparse, hashlib, subprocess, tempfile
from pathlib import Path

p = argparse.ArgumentParser()
p.add_argument('--cpu', help='optional rustc target CPU, e.g. x86-64-v3')
p.add_argument('--extremes', action='store_true')
a = p.parse_args()
here = Path(__file__).resolve().parent
root = here.parents[1]
src = (here / 'candidate.rs').read_text()
expected = 'd74c9104ddb3ce661e1e597276c2bb9da621a73bbe6846cd82f901de719c1d64'
assert hashlib.sha256(src.encode()).hexdigest() == expected

def run(*args):
    subprocess.run([str(x) for x in args], check=True)

with tempfile.TemporaryDirectory(prefix='d-compact-loader-') as temp:
    temp = Path(temp)
    binary = temp / 'candidate'
    flags = ['rustc', '--edition=2021', '-O', '-C', 'overflow-checks=yes', '-C', 'debug-assertions=yes']
    if a.cpu: flags += ['-C', f'target-cpu={a.cpu}']
    run(*flags, here / 'candidate.rs', '-o', binary)
    prop = temp / 'property.rs'; prop.write_text(src + '\n' + (here / 'property-tail.rs').read_text())
    run(*flags, '--test', prop, '-o', temp / 'property'); run(temp / 'property')
    for name in ('oracle.py', 'exhaustive.py'):
        run('python3', root / 'experiments/track-d-balanced-frontier' / name, binary)
    run('python3', root / 'experiments/track-d-packed32-adj/boundaries.py', binary)
    if a.extremes: run('python3', root / 'experiments/track-d-balanced-frontier/extremes.py', binary)
print('PASS compact staging properties, exact graph oracles and node/weight boundaries')
