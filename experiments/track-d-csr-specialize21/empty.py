#!/usr/bin/env python3
"""Test empty adjacency in compact-size and wide-size graph modes."""
import os, subprocess, sys, tempfile
from pathlib import Path
for n in (1,2,2**21,2**21+1):
 with tempfile.TemporaryDirectory() as tmp:
  p=Path(tmp);(p/'graph.txt').write_text(f'{n} 0\n');(p/'queries.txt').write_text('0 0\n'+(f'0 {n-1}\n{n-1} 0\n' if n>1 else ''));(p/'out').mkdir()
  subprocess.run([str(Path(sys.argv[1]).resolve())],env=dict(os.environ,SD_DATA=tmp,SD_OUT=str(p/'out')),check=True)
  expected='0\n'+('-1\n-1\n' if n>1 else '')
  assert (p/'out/distances.txt').read_text()==expected
print('PASS empty edges, n=1/2/2^21/2^21+1')
