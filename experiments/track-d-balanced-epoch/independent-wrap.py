#!/usr/bin/env python3
"""Exercise packed-epoch rollover, self queries and directed edge cases.

Supply a candidate built with one query worker so each non-self query shares
one epoch counter. The graph has duplicate and zero-weight edges, maximum
u32 weights, and unreachable directed pairs. No generated answers are used
by the candidate.
"""
import hashlib
import os
from pathlib import Path
import subprocess
import sys
import tempfile

if len(sys.argv) != 2:
    raise SystemExit('usage: independent-wrap.py SINGLE_WORKER_BINARY')
binary = Path(sys.argv[1]).resolve(strict=True)
w = 4294967295
edges = [(0, 1, w), (1, 2, 0), (2, 1, 1), (1, 1, 0), (0, 1, w)]
answers = {(0, 0): 0, (1, 1): 0, (2, 2): 0, (0, 1): w,
           (0, 2): w, (1, 2): 0, (2, 1): 1, (1, 0): -1, (2, 0): -1}
queries = []
for _ in range(12):
    for j in range(2047):
        queries.append(((0, 2), (2, 0), (1, 2), (2, 1))[j % 4])
    queries.extend([(0, 0), (1, 1), (2, 2), (0, 2), (2, 0)])
with tempfile.TemporaryDirectory(prefix='epoch-independent-') as temp:
    root = Path(temp)
    data, out = root / 'data', root / 'out'
    data.mkdir()
    out.mkdir()
    (data / 'graph.txt').write_text('3 5\n' + ''.join(f'{u} {v} {weight}\n' for u, v, weight in edges))
    (data / 'queries.txt').write_text(''.join(f'{u} {v}\n' for u, v in queries))
    subprocess.run([str(binary)], check=True, env=dict(os.environ, SD_DATA=str(data), SD_OUT=str(out)))
    actual = (out / 'distances.txt').read_bytes()
    expected = ''.join(f'{answers[q]}\n' for q in queries).encode()
    if actual != expected:
        raise SystemExit('FAIL independent rollover output')
    print(f'PASS {len(queries)} queries / 12 epoch-boundary blocks; SHA256 {hashlib.sha256(actual).hexdigest()}')
