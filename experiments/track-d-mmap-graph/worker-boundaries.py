#!/usr/bin/env python3
"""Compile checked forced-worker candidates and exercise n=1 and graph oracles."""
import os
from pathlib import Path
import subprocess
import tempfile

source = Path('experiments/track-d-mmap-graph/meeting.rs').read_text()
needle = 'let threads = thread::available_parallelism().map_or(1, |n| n.get());'
assert source.count(needle) == 1
with tempfile.TemporaryDirectory(prefix='d-fastblock-workers-') as tmp:
    base = Path(tmp)
    data = base / 'data'
    out = base / 'out'
    data.mkdir()
    out.mkdir()
    # Plenty of complete lines even at the largest worker count.
    (data / 'graph.txt').write_text('1 64\n' + ''.join(f'0 0 {w}\n' for w in range(64)))
    (data / 'queries.txt').write_text('0 0\n' * 128)
    for workers in (1, 2, 3, 7, 12, 32):
        candidate = base / 'candidate.rs'
        binary = base / 'candidate'
        candidate.write_text(source.replace(needle, f'let threads = {workers}usize;'))
        subprocess.run(['rustc','--edition=2021','-C','opt-level=2','-C','overflow-checks=yes',str(candidate),'-o',str(binary)],check=True)
        env = dict(os.environ, SD_DATA=str(data), SD_OUT=str(out))
        subprocess.run([str(binary)],env=env,check=True)
        assert (out / 'distances.txt').read_text() == '0\n' * 128
        subprocess.run(['python3','experiments/track-d-balanced-frontier/oracle.py',str(binary)],check=True)
        print(f'PASS n=1 and random oracle at workers={workers}',flush=True)
