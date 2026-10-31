#!/usr/bin/env python3
"""Compare compiled baseline and variant on full seed 1; timings are non-official."""
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

EXPECTED = '495ca09682b9673ef836a506496177680bb4a3af54255174befddb1f83481cd3'
p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--baseline', required=True, type=Path)
p.add_argument('--variant', required=True, type=Path)
p.add_argument('--data', required=True, type=Path)
p.add_argument('--runs', type=int, default=6)
p.add_argument('--threads', type=int, help='force the same SD_THREADS in both binaries; default uses available parallelism')
p.add_argument('--report', required=True, type=Path)
a = p.parse_args()
if a.runs < 1:
    p.error('--runs must be positive')
if a.threads is not None and a.threads < 1:
    p.error('--threads must be positive')
bins = {k: str(v.resolve()) for k, v in {'baseline': a.baseline, 'variant': a.variant}.items()}
results = {k: [] for k in bins}
rng = random.Random(818)
with tempfile.TemporaryDirectory(prefix='a-pgo-') as tmp:
    for iteration in range(a.runs + 1):
        order = list(bins)
        rng.shuffle(order)
        for label in order:
            output = Path(tmp) / 'summary.txt'
            output.unlink(missing_ok=True)
            env = dict(os.environ, SD_DATA=str(a.data.resolve()), SD_OUT=tmp)
            env.pop('SD_THREADS', None)
            if a.threads is not None:
                env['SD_THREADS'] = str(a.threads)
            start = time.perf_counter()
            proc = subprocess.Popen([bins[label]], env=env)
            _, status, usage = os.wait4(proc.pid, 0)
            proc.returncode = os.waitstatus_to_exitcode(status)
            elapsed = time.perf_counter() - start
            if proc.returncode != 0 or hashlib.sha256(output.read_bytes()).hexdigest() != EXPECTED:
                raise RuntimeError(f'{label} failed or output hash mismatched')
            if iteration:
                results[label].append({'wall_s': elapsed, 'cpu_s': usage.ru_utime + usage.ru_stime,
                                       'max_rss_native_units': usage.ru_maxrss})
report = {'threads_override': a.threads, 'measurements': results, 'max_rss_note': 'Linux: KiB; macOS: bytes; process RSS, not cgroup'}
for label, rows in results.items():
    report[label + '_median_wall_s'] = statistics.median(r['wall_s'] for r in rows)
    report[label + '_median_cpu_s'] = statistics.median(r['cpu_s'] for r in rows)
a.report.write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps(report, indent=2))
