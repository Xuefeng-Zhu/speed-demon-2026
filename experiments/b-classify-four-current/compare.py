#!/usr/bin/env python3
"""Compare compiled Rust B binaries; native timing is not official cgroup scoring."""
import argparse, hashlib, json, os, random, statistics, subprocess, tempfile, time
from pathlib import Path

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--baseline', type=Path, required=True)
p.add_argument('--candidate', type=Path, required=True)
p.add_argument('--data', type=Path, required=True)
p.add_argument('--runs', type=int, default=6)
p.add_argument('--report', type=Path)
p.add_argument('--seed', type=int, default=1234)
a = p.parse_args()
if a.runs < 1:
    p.error('runs must be positive')
binaries = {k: str(getattr(a, k).resolve(strict=True)) for k in ('baseline', 'candidate')}
data = str(a.data.resolve(strict=True))
expected = 'f86973c210228141bcb6f1f1b10188ad2a9b65f71e7cd7cf4590b38de4e80927'
results = {k: [] for k in binaries}
with tempfile.TemporaryDirectory(prefix='b-rust-clauses-') as temp:
    for i in range(a.runs + 1):
        order = list(binaries)
        random.Random(a.seed + i).shuffle(order)
        for name in order:
            out = Path(temp) / f'{i}-{name}'
            out.mkdir()
            env = dict(os.environ, SD_DATA=data, SD_OUT=str(out))
            start = time.perf_counter()
            proc = subprocess.Popen([binaries[name]], env=env, stdout=subprocess.DEVNULL)
            _, status, usage = os.wait4(proc.pid, 0)
            elapsed = time.perf_counter() - start
            if os.waitstatus_to_exitcode(status):
                raise SystemExit(f'{name} failed: status {status}')
            digest = hashlib.sha256((out / 'results.txt').read_bytes()).hexdigest()
            if digest != expected:
                raise SystemExit(f'{name} produced incorrect hash {digest}')
            results[name].append({'wall_s': elapsed, 'cpu_s': usage.ru_utime + usage.ru_stime,
                                  'max_rss_native': usage.ru_maxrss, 'warmup': i == 0})
for name, samples in results.items():
    print(name, 'median_wall_s', statistics.median(x['wall_s'] for x in samples[1:]),
          'median_cpu_s', statistics.median(x['cpu_s'] for x in samples[1:]))
if a.report:
    a.report.write_text(json.dumps(results, indent=2) + '\n')
