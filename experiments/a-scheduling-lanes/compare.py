#!/usr/bin/env python3
"""Interleave two already-built A binaries; verify each output hash."""
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
p.add_argument('--baseline', type=Path, required=True)
p.add_argument('--candidate', type=Path, required=True)
p.add_argument('--data', type=Path, required=True)
p.add_argument('--report', type=Path, required=True)
p.add_argument('--workers', type=int, default=12)
p.add_argument('--runs', type=int, default=12)
p.add_argument('--warmups', type=int, default=2)
p.add_argument('--expected', default='495ca09682b9673ef836a506496177680bb4a3af54255174befddb1f83481cd3')
a = p.parse_args()
if min(a.workers, a.runs) < 1 or a.warmups < 0:
    p.error('workers and runs must be positive, warmups nonnegative')
binaries = {'baseline': a.baseline.resolve(strict=True), 'candidate': a.candidate.resolve(strict=True)}
data = a.data.resolve(strict=True)
expected = a.expected.lower()
if len(expected) != 64 or any(c not in '0123456789abcdef' for c in expected):
    p.error('expected must be a SHA-256 digest')
rows = []
rng = random.Random(11617)
with tempfile.TemporaryDirectory(prefix='a-scheduling-compare-') as temp:
    root = Path(temp)
    for i in range(-a.warmups, a.runs):
        order = list(binaries)
        rng.shuffle(order)
        for label in order:
            out = root / f'{label}-{i}'
            out.mkdir()
            env = dict(os.environ, SD_DATA=str(data), SD_OUT=str(out), SD_THREADS=str(a.workers))
            start = time.perf_counter()
            proc = subprocess.Popen([str(binaries[label])], env=env, stdout=subprocess.DEVNULL)
            _, status, usage = os.wait4(proc.pid, 0)
            elapsed = time.perf_counter() - start
            proc.returncode = os.waitstatus_to_exitcode(status)
            if proc.returncode:
                raise SystemExit(f'{label}: exit {proc.returncode}')
            outputs = list(out.iterdir())
            if len(outputs) != 1 or outputs[0].name != 'summary.txt':
                raise SystemExit(f'{label}: unexpected output files {outputs}')
            with outputs[0].open('rb') as f:
                digest = hashlib.file_digest(f, 'sha256').hexdigest()
            if digest != expected:
                raise SystemExit(f'{label}: incorrect output SHA-256 {digest}')
            rows.append({'variant': label, 'iteration': i, 'wall_s': elapsed,
                         'user_s': usage.ru_utime, 'system_s': usage.ru_stime,
                         'max_rss_native_units': usage.ru_maxrss})
summary = {}
for label in binaries:
    measured = [r for r in rows if r['variant'] == label and r['iteration'] >= 0]
    summary[label] = {'median_wall_s': statistics.median(r['wall_s'] for r in measured),
                      'median_cpu_s': statistics.median(r['user_s'] + r['system_s'] for r in measured),
                      'max_rss_native_units': max(r['max_rss_native_units'] for r in measured)}
report = {'workers': a.workers, 'runs': a.runs, 'warmups': a.warmups,
          'expected_sha256': expected, 'rss_note': 'wait4 process peak RSS, not cgroup memory; Linux KiB, macOS bytes',
          'summary': summary, 'measurements': rows}
a.report.write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps(summary, indent=2))
