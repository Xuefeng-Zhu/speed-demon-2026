#!/usr/bin/env python3
"""Instrument actual lane cursors and compare reference; no timing claims."""
import argparse
import collections
import datetime
import os
from pathlib import Path
import random
import subprocess
import tempfile

p = argparse.ArgumentParser()
p.add_argument('--darwin', action='store_true')
p.add_argument('--force-collision', action='store_true')
args = p.parse_args()
here = Path(__file__).resolve().parent
root = here.parents[1]
source = (here / 'candidate.rs').read_text()
if args.darwin:
    old = '(1, 2, 0x10, 0x20, std::ptr::null_mut())'
    assert source.count(old) == 1
    source = source.replace(old, '(1, 2, 0x10, 0x1000, std::ptr::null_mut())')
one = 'fn one(d: &[u8], i: usize, c: &mut Chunk) -> usize {'
pair = '    while a < mid && b < end {'
assert source.count(one) == source.count(pair) == 1
source = source.replace(one, one + '\n    eprintln!("@one {}", i);')
source = source.replace(pair, pair + '\n        eprintln!("@pair {} {}", a, b);')
if args.force_collision:
    marker = '    fn find(&mut self, d: &[u8], h: u64, s: usize, e: usize) -> usize {'
    assert source.count(marker) == 1
    source = source.replace(marker, marker + '\n        let h = 0u64;')

base = datetime.datetime(2026, 10, 30, 18)
methods = ('GET', 'POST', 'PUT', 'PATCH', 'DELETE', 'HEAD', 'OPTIONS')
lat = (0, 1, 1048574, 1048575, 1048576, 4294967295)
status = (100, 499, 500, 599)

def corpus(count, seed, nendpoints):
    rng = random.Random(seed)
    result = []
    for i in range(count):
        endpoint = '/' + (('a' * ((i % 125))) if i % 7 == 0 else f'id/{i % nendpoints:04}')
        dt = base + datetime.timedelta(hours=(i * 17) % 72, seconds=rng.randrange(3600), microseconds=i % 1000000)
        line = dt.strftime('%Y-%m-%dT%H:%M:%S.%fZ') + f' {methods[i % 7]} {endpoint} {status[i % 4]} {lat[(i // 4) % len(lat)]}\n'
        if i > 0 and i % 23 == 0:
            line = result[-1]  # Duplicate records must still be visited separately.
        result.append(line)
    return ''.join(result).encode('ascii')

with tempfile.TemporaryDirectory(prefix='a-two-lane-coverage-') as td:
    d = Path(td); (d / 'data').mkdir(); (d / 'out').mkdir(); (d / 'ref').mkdir()
    (d / 'test.rs').write_text(source)
    subprocess.run(['rustc', '--edition=2021', '-O', '-C', 'panic=abort', d / 'test.rs', '-o', d / 'test'], check=True)
    checked = 0
    for count, seed, endpoints in [(0, 0, 1), (1, 1, 1), (2, 2, 2), (3, 3, 3), (7, 4, 7), (31, 5, 31), (127, 6, 127), (2500, 7, 2422)]:
        data = corpus(count, seed, endpoints)
        (d / 'data/requests.log').write_bytes(data)
        subprocess.run(['python3', root / 'official/reference/a_ingest.py', '--data', d / 'data', '--out', d / 'ref'], check=True)
        starts = []; pos = 0
        for line in data.splitlines(keepends=True):
            starts.append(pos); pos += len(line)
        for threads in (1, 2, 3, 7, 12, 32):
            env = {**os.environ, 'SD_DATA': str(d/'data'), 'SD_OUT': str(d/'out'), 'SD_THREADS': str(threads)}
            proc = subprocess.run([d/'test'], env=env, text=True, capture_output=True, check=True)
            visited = []
            for line in proc.stderr.splitlines():
                fields = line.split()
                if fields and fields[0] in ('@one', '@pair'):
                    visited.extend(map(int, fields[1:]))
            assert collections.Counter(visited) == collections.Counter(starts), (count, threads, len(visited), len(starts))
            assert (d/'out/summary.txt').read_bytes() == (d/'ref/summary.txt').read_bytes(), (count, threads)
            checked += 1
print(f'PASS {checked} actual-source lane coverage/reference checks; forced_collision={args.force_collision}')
