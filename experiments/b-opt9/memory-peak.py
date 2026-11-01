#!/usr/bin/env python3
"""Compare fresh Linux container cgroup peaks; validate every full-data output."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import random
import statistics
import subprocess
import tempfile

EXPECTED = 'f86973c210228141bcb6f1f1b10188ad2a9b65f71e7cd7cf4590b38de4e80927'
p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--binary', action='append', required=True, help='name=/absolute/binary')
p.add_argument('--data', default='/tmp/speed-b-full')
p.add_argument('--expected', default=EXPECTED)
p.add_argument('--image', required=True)
p.add_argument('--platform', default='linux/arm64')
p.add_argument('--runs', type=int, default=5)
p.add_argument('--threads', type=int, default=12)
p.add_argument('--report', required=True)
a = p.parse_args()
binaries = dict(s.split('=', 1) for s in a.binary)
rows = []
rng = random.Random(9)
with tempfile.TemporaryDirectory(prefix='b-opt9-cgroup-') as tmp:
    for rep in range(-1, a.runs):
        names = list(binaries)
        rng.shuffle(names)
        for name in names:
            out = Path(tmp, f'{rep}-{name}')
            out.mkdir(mode=0o777)
            out.chmod(0o777)
            command = [
                'docker', 'run', '--rm', '--platform', a.platform, '--network', 'none',
                '--read-only', '--user', '65534:65534', '--cap-drop', 'ALL',
                '--security-opt', 'no-new-privileges', '--memory', '1g', '--pids-limit', '64',
                '--tmpfs', '/tmp:rw,size=1g',
                '--mount', f'type=bind,src={Path(a.data).resolve()},dst=/data,readonly',
                '--mount', f'type=bind,src={Path(binaries[name]).resolve()},dst=/app/solution,readonly',
                '--mount', f'type=bind,src={out},dst=/out',
                '--env', f'SD_THREADS={a.threads}', '--entrypoint', 'sh', a.image,
                '-c', '/app/solution; rc=$?; read peak < /sys/fs/cgroup/memory.peak; '
                      'printf "PEAK %s\\n" "$peak"; exit "$rc"',
            ]
            proc = subprocess.run(command, text=True, capture_output=True, timeout=90)
            assert proc.returncode == 0, (name, proc.returncode, proc.stderr)
            peak = int(proc.stdout.strip().removeprefix('PEAK '))
            digest = hashlib.sha256((out / 'results.txt').read_bytes()).hexdigest()
            assert digest == a.expected, (name, digest)
            assert sorted(f.name for f in out.iterdir()) == ['results.txt']
            rows.append(dict(rep=rep, name=name, cgroup_peak_bytes=peak, sha256=digest))
        print(f'round {rep + 1}/{a.runs}', flush=True)
summary = {}
for name in binaries:
    peaks = [r['cgroup_peak_bytes'] for r in rows if r['name'] == name and r['rep'] >= 0]
    summary[name] = dict(median_bytes=statistics.median(peaks), max_bytes=max(peaks), min_bytes=min(peaks))
result = dict(platform=a.platform, image=a.image, threads=a.threads, data=a.data,
              expected_sha256=a.expected, rows=rows, summary=summary,
              note='Fresh local container memory.peak, including a waiting shell; not official board M.')
Path(a.report).write_text(json.dumps(result, indent=2) + '\n')
print(json.dumps(summary, indent=2))
