#!/usr/bin/env python3
"""Exercise exact 32-bit cutoff and fallback behavior for a D executable."""
from pathlib import Path
import os
import subprocess
import sys
import tempfile

binary = Path(sys.argv[1]).resolve(strict=True)
with tempfile.TemporaryDirectory(prefix='d-u32-bound-') as t:
    p = Path(t)
    (p / 'graph.txt').write_text('7 8\n0 1 4294967294\n0 2 4294967295\n0 3 4294967295\n3 4 1\n1 4 1\n0 5 0\n5 1 4294967294\n3 6 1\n')
    (p / 'queries.txt').write_text('0 1\n0 2\n0 4\n0 6\n0 5\n5 2\n1 4\n5 5\n')
    (p / 'out').mkdir()
    subprocess.run([str(binary)], env=dict(os.environ, SD_DATA=str(p), SD_OUT=str(p / 'out')), check=True)
    expected = '4294967294\n4294967295\n4294967295\n4294967296\n0\n-1\n1\n0\n'
    assert (p / 'out/distances.txt').read_text() == expected
print('PASS cutoff-1, cutoff, cutoff+1, unreachable, zero and self')
