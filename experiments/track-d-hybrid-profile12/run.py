#!/usr/bin/env python3
"""Randomized pairs of uninstrumented and diagnostic D; records raw data."""
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

p = argparse.ArgumentParser()
p.add_argument('--baseline', required=True)
p.add_argument('--profile', required=True)
p.add_argument('--data', type=Path, required=True)
p.add_argument('--report', type=Path, required=True)
p.add_argument('--pairs', type=int, default=5)
args = p.parse_args()
expected = 'a23dbdf0a3e49cc8901310a9ee1dc6a9a569a85297b6da75c2a7002cb2ed277e'
bins = {'baseline': str(Path(args.baseline).resolve()), 'profile': str(Path(args.profile).resolve())}
results = []
rng = random.Random(861729)
with tempfile.TemporaryDirectory(prefix='d-hybrid-phase-') as tmp:
    out = Path(tmp)
    for i in range(-1, args.pairs):
        order = list(bins)
        rng.shuffle(order)
        for label in order:
            result_file = out / 'distances.txt'
            result_file.unlink(missing_ok=True)
            with tempfile.TemporaryFile(mode='w+b') as err:
                start = time.monotonic()
                proc = subprocess.Popen([bins[label]], env={**os.environ, 'SD_DATA': str(args.data.resolve()), 'SD_OUT': str(out)}, stdout=subprocess.DEVNULL, stderr=err)
                _, status, usage = os.wait4(proc.pid, 0)
                proc.returncode = os.waitstatus_to_exitcode(status)
                wall = time.monotonic() - start
                if not os.WIFEXITED(status) or os.WEXITSTATUS(status) != 0:
                    err.seek(0)
                    raise RuntimeError(f'{label} failed {status}: {err.read().decode(errors="replace")}')
                digest = hashlib.sha256(result_file.read_bytes()).hexdigest()
                if digest != expected:
                    raise RuntimeError(f'{label} wrong SHA-256: {digest}')
                err.seek(0)
                diagnostic = err.read().decode()
            results.append({'pair': i, 'label': label, 'wall_s': wall, 'cpu_s': usage.ru_utime + usage.ru_stime,
                            'maxrss_native': usage.ru_maxrss, 'sha256': digest, 'stderr': diagnostic})
summary = {}
for label in bins:
    measured = [r for r in results if r['label'] == label and r['pair'] >= 0]
    summary[label] = {k: statistics.median(r[k] for r in measured) for k in ('wall_s', 'cpu_s', 'maxrss_native')}
args.report.write_text(json.dumps({'note': 'native ARM; instrumentation perturbs timings; RSS is process, not cgroup',
                                   'source_sha256': '671c639be3400209e83e080dfb54947affd30ca71dc34ec17804d24d70292d9c',
                                   'results': results, 'summary': summary}, indent=2) + '\n')
print(json.dumps(summary, indent=2))
