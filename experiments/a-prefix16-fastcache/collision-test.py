#!/usr/bin/env python3
"""Compare exact A results on shared-prefix, hint-collision and length boundaries."""
import argparse
import datetime
import os
from pathlib import Path
import random
import subprocess
import tempfile

p = argparse.ArgumentParser()
p.add_argument('--binary', action='append', required=True)
p.add_argument('--reference', required=True)
a = p.parse_args()
rng = random.Random(472901)
prefix = '/same-prefix-123'
assert len(prefix) == 16
names = ['/' + 'Z' * (n - 1) for n in (1, 7, 8, 9, 15, 16, 17, 31, 32, 63, 64, 125)]
names += [prefix, prefix + 'x', prefix + 'y' * 109]
names += [prefix + f'/route{i:04}' for i in range(2300)]
assert max(map(len, names)) <= 125 and len(set(names)) == len(names)
methods = ['GET', 'POST', 'PUT', 'PATCH', 'DELETE', 'HEAD', 'OPTIONS']
statuses = [200, 499, 500, 599]
latencies = [0, 1, 1048574, 1048575, 4294967295]
start = datetime.datetime(2026, 10, 30, 18)
with tempfile.TemporaryDirectory(prefix='a-prefix16-collision-') as temp:
    root = Path(temp)
    data, expected, out = (root / x for x in ('data', 'expected', 'out'))
    for d in (data, expected, out): d.mkdir()
    with (data / 'requests.log').open('w', encoding='ascii') as f:
        for i in range(40000):
            name = names[i % len(names)] if i < 2303 else rng.choice(names)
            when = start + datetime.timedelta(hours=(i * 17) % 72, seconds=(i * 313) % 3600)
            f.write(when.strftime('%Y-%m-%dT%H:%M:%S.000000Z') +
                    f' {methods[i % len(methods)]} {name} {statuses[i % 4]} {latencies[i % 5]}\n')
    subprocess.run(['python3', a.reference, '--data', str(data), '--out', str(expected)], check=True,
                   stdout=subprocess.DEVNULL)
    want = (expected / 'summary.txt').read_bytes()
    for binary in a.binary:
        for workers in (1, 2, 7, 12, 32):
            subprocess.run([binary], check=True,
                           env={**os.environ, 'SD_DATA': str(data), 'SD_OUT': str(out), 'SD_THREADS': str(workers)})
            assert (out / 'summary.txt').read_bytes() == want, (binary, workers)
            print('PASS', Path(binary).name, 'workers', workers, flush=True)
