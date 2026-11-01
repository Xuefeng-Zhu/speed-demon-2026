#!/usr/bin/env python3
"""Interleave full-data candidates; verify every output and retain raw rusage.

Local iteration evidence only. Darwin reports ru_maxrss in bytes, Linux in KiB.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import random
import statistics
import subprocess
import tempfile
import time

EXPECTED = 'f86973c210228141bcb6f1f1b10188ad2a9b65f71e7cd7cf4590b38de4e80927'
p = argparse.ArgumentParser()
p.add_argument('--binary', action='append', required=True, help='name=/absolute/binary')
p.add_argument('--data', default='/tmp/speed-b-full')
p.add_argument('--runs', type=int, default=11)
p.add_argument('--threads', type=int, default=8)
p.add_argument('--report', required=True)
a = p.parse_args()
binaries = dict(s.split('=', 1) for s in a.binary)
rng = random.Random(8)
rows = []
with tempfile.TemporaryDirectory(prefix='b-opt8-bench-') as out:
    for rep in range(-1, a.runs):
        names = list(binaries)
        rng.shuffle(names)
        for name in names:
            env = dict(os.environ, SD_DATA=a.data, SD_OUT=out, SD_THREADS=str(a.threads))
            start = time.perf_counter()
            proc = subprocess.Popen([binaries[name]], env=env, stderr=subprocess.PIPE)
            _, status, usage = os.wait4(proc.pid, 0)
            elapsed = time.perf_counter() - start
            proc.returncode = os.waitstatus_to_exitcode(status)
            stderr = proc.stderr.read().decode(errors='replace')
            assert proc.returncode == 0, (name, proc.returncode, stderr)
            digest = hashlib.sha256(Path(out, 'results.txt').read_bytes()).hexdigest()
            assert digest == EXPECTED, (name, digest)
            row = dict(rep=rep, name=name, wall_s=elapsed, cpu_s=usage.ru_utime + usage.ru_stime,
                       rss_bytes=usage.ru_maxrss * (1 if platform.system() == 'Darwin' else 1024),
                       minor_faults=usage.ru_minflt, sha256=digest)
            rows.append(row)
        print(f'round {rep + 1}/{a.runs}', flush=True)
summary = {}
for name in binaries:
    rr = [r for r in rows if r['name'] == name and r['rep'] >= 0]
    summary[name] = {k: statistics.median(r[k] for r in rr)
                     for k in ('wall_s', 'cpu_s', 'rss_bytes', 'minor_faults')}
result = dict(platform=platform.platform(), machine=platform.machine(), threads=a.threads,
              binaries={n: dict(path=f, sha256=hashlib.sha256(Path(f).read_bytes()).hexdigest())
                        for n, f in binaries.items()}, rows=rows, summary=summary)
Path(a.report).write_text(json.dumps(result, indent=2) + '\n')
print(json.dumps(summary, indent=2))
