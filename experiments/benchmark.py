#!/usr/bin/env python3
"""Interleaved local benchmark with output-hash verification after each run.

Example: python3 experiments/benchmark.py --baseline '/tmp/a-old /tmp/data/requests.log /tmp/bench-a.txt' --candidate '/tmp/a-new /tmp/data/requests.log /tmp/bench-a.txt' --output /tmp/bench-a.txt --expected HASH
"""
import argparse
import hashlib
import json
import os
import platform
import resource
import shlex
import statistics
import subprocess
import sys
import time
from pathlib import Path

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--baseline', required=True, help='command and arguments, parsed with shlex')
p.add_argument('--candidate', required=True, help='command and arguments, parsed with shlex')
p.add_argument('--output', required=True, help='output file produced by each command')
p.add_argument('--expected', required=True, help='expected SHA-256')
p.add_argument('--runs', type=int, default=5, help='measured runs of each variant')
p.add_argument('--warmups', type=int, default=1)
p.add_argument('--report', help='optional output JSON path')
a = p.parse_args()
if a.runs < 1 or a.warmups < 0:
    p.error('runs must be positive and warmups nonnegative')
commands = {k: shlex.split(getattr(a, k)) for k in ('baseline', 'candidate')}
result = {'system': platform.platform(), 'machine': platform.machine(), 'python': sys.version,
          'commands': commands, 'output': a.output, 'expected_sha256': a.expected,
          'warmups': a.warmups, 'runs': a.runs, 'measurements': {'baseline': [], 'candidate': []}}
for iteration in range(-a.warmups, a.runs):
    order = ('baseline', 'candidate') if iteration % 2 == 0 else ('candidate', 'baseline')
    for name in order:
        Path(a.output).unlink(missing_ok=True)
        before = resource.getrusage(resource.RUSAGE_CHILDREN)
        start = time.perf_counter()
        subprocess.run(commands[name], check=True, stdout=subprocess.DEVNULL)
        elapsed = time.perf_counter() - start
        after = resource.getrusage(resource.RUSAGE_CHILDREN)
        digest = hashlib.file_digest(open(a.output, 'rb'), 'sha256').hexdigest()
        if digest != a.expected.lower():
            raise SystemExit(f'{name} iteration {iteration}: incorrect output hash {digest}')
        sample = {'wall_s': round(elapsed, 6), 'user_s': round(after.ru_utime - before.ru_utime, 6),
                  'system_s': round(after.ru_stime - before.ru_stime, 6)}
        if iteration >= 0:
            result['measurements'][name].append(sample)
            print(f'{name} {iteration + 1}: {sample}', flush=True)
for name, measurements in result['measurements'].items():
    result[name + '_median_wall_s'] = statistics.median(m['wall_s'] for m in measurements)
result['median_wall_speedup'] = result['baseline_median_wall_s'] / result['candidate_median_wall_s']
print(json.dumps(result, indent=2))
if a.report:
    Path(a.report).write_text(json.dumps(result, indent=2) + '\n')
