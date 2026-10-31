#!/usr/bin/env python3
"""Check max representable path and force packed epoch rollover in a single worker."""
import argparse
import os
from pathlib import Path
import subprocess
import tempfile

p = argparse.ArgumentParser()
p.add_argument('--binary', required=True, help='normal packed executable')
p.add_argument('--single-binary', required=True, help='packed executable built with one worker')
a = p.parse_args()

def run(binary, data, out):
    subprocess.run([binary], env={**os.environ, 'DATA_DIR': str(data), 'OUT_DIR': str(out)}, check=True)
    return (out / 'distances.txt').read_text().splitlines()

def graph(data, n):
    with (data / 'graph.txt').open('w', buffering=1024 * 1024) as f:
        f.write(f'{n} {n - 1}\n')
        for i in range(n - 1):
            f.write(f'{i} {i + 1} 4294967295\n')

with tempfile.TemporaryDirectory(prefix='d-packed-extremes-') as temp:
    root = Path(temp)
    data, out = root / 'data', root / 'out'
    data.mkdir()
    out.mkdir()
    n = 1_740_512
    graph(data, n)
    (data / 'queries.txt').write_text(f'0 {n - 1}\n{n - 1} 0\n0 0\n')
    assert run(a.binary, data, out) == [str((n - 1) * 4294967295), '-1', '0']
    print('PASS full-size max-weight chain, reverse unreachable, and self query')
    n = 5000
    graph(data, n)
    # Exactly 3,000 of these pairs enter the search; this crosses the 2,047 epoch reset.
    (data / 'queries.txt').write_text(('0 4999\n4999 0\n') * 3000)
    assert run(a.single_binary, data, out) == [str(4999 * 4294967295), '-1'] * 3000
    print('PASS 6,000 queries on one worker across epoch reset')
