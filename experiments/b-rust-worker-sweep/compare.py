#!/usr/bin/env python3
"""Screen B worker counts with native hash-checked runs (not cgroup scoring)."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import random
import statistics
import subprocess
import tempfile
import time

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--binary', type=Path, required=True, help='compiled test-override.rs')
p.add_argument('--data', type=Path, required=True)
p.add_argument('--counts', type=int, nargs='+', default=[3, 6, 8, 9, 12, 16])
p.add_argument('--runs', type=int, default=5)
p.add_argument('--report', type=Path)
a = p.parse_args()
if a.runs < 1 or not a.counts or any(n < 1 for n in a.counts) or len(set(a.counts)) != len(a.counts):
    p.error('runs and distinct counts must be positive')
binary = str(a.binary.resolve(strict=True))
data = str(a.data.resolve(strict=True))
expected = 'f86973c210228141bcb6f1f1b10188ad2a9b65f71e7cd7cf4590b38de4e80927'
result = {str(n): [] for n in a.counts}
with tempfile.TemporaryDirectory(prefix='b-worker-sweep-') as td:
    for i in range(a.runs + 1):
        order = a.counts[:]
        random.Random(1234 + i).shuffle(order)
        for n in order:
            out = Path(td) / f'{i}-{n}'
            out.mkdir()
            env = dict(os.environ, SD_DATA=data, SD_OUT=str(out), SD_TEST_THREADS=str(n))
            start = time.perf_counter()
            proc = subprocess.Popen([binary], env=env, stdout=subprocess.DEVNULL)
            _, status, usage = os.wait4(proc.pid, 0)
            wall = time.perf_counter() - start
            if os.waitstatus_to_exitcode(status):
                raise SystemExit(f'worker={n} iteration={i}: status {status}')
            digest = hashlib.sha256((out / 'results.txt').read_bytes()).hexdigest()
            if digest != expected:
                raise SystemExit(f'worker={n} iteration={i}: wrong SHA-256 {digest}')
            result[str(n)].append({'wall_s': wall, 'cpu_s': usage.ru_utime + usage.ru_stime,
                                   'max_rss_native': usage.ru_maxrss, 'warmup': i == 0})
for n in a.counts:
    rows = result[str(n)][1:]
    print(n, 'median_wall_s', statistics.median(r['wall_s'] for r in rows),
          'median_cpu_s', statistics.median(r['cpu_s'] for r in rows),
          'max_rss_native', max(r['max_rss_native'] for r in rows))
if a.report:
    a.report.write_text(json.dumps(result, indent=2) + '\n')
