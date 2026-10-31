#!/usr/bin/env python3
"""Randomized native D comparator; process RSS is not cgroup memory."""
import argparse, hashlib, json, os, platform, random, statistics, subprocess, tempfile, time
from pathlib import Path

p = argparse.ArgumentParser()
p.add_argument('--data', type=Path, required=True)
p.add_argument('--build-dir', type=Path, required=True)
p.add_argument('--report', type=Path, required=True)
p.add_argument('--runs', type=int, default=9)
p.add_argument('--names', nargs='+', default=['baseline', 'candidate'])
p.add_argument('--expected', default='a4c76ed030bc7e365db33191f6cf74708fba7f25eb48d64c8c4279f2e57046a0')
p.add_argument('--seed', type=int, default=1948)
a = p.parse_args()
assert a.runs > 0 and a.data.is_dir() and all(x in {'baseline','candidate'} for x in a.names)
root = Path(__file__).resolve().parent
a.build_dir.mkdir(parents=True, exist_ok=True)
bins = {}
flags = ['--edition=2021', '-C', 'opt-level=3', '-C', 'lto=fat', '-C', 'codegen-units=1', '-C', 'panic=abort']
if platform.machine().lower() in ('x86_64', 'amd64'): flags += ['-C', 'target-cpu=x86-64-v3']
for name in a.names:
    bins[name] = (a.build_dir / name).resolve()
    subprocess.run(['rustc', *flags, str(root / (name + '.rs')), '-o', str(bins[name])], check=True)
rows = []
rng = random.Random(a.seed)
with tempfile.TemporaryDirectory(prefix='d-batch-') as tmp:
    env = dict(os.environ, SD_DATA=str(a.data.resolve()), SD_OUT=tmp)
    output = Path(tmp) / 'distances.txt'
    for i in range(-1, a.runs):
        names = list(a.names)
        rng.shuffle(names)
        for name in names:
            output.unlink(missing_ok=True)
            start = time.monotonic()
            proc = subprocess.Popen([str(bins[name])], env=env)
            _, status, usage = os.wait4(proc.pid, 0)
            wall = time.monotonic() - start
            if os.waitstatus_to_exitcode(status) != 0: raise RuntimeError((name, status))
            digest = hashlib.sha256(output.read_bytes()).hexdigest()
            if digest != a.expected: raise RuntimeError((name, digest))
            rows.append(dict(iteration=i, name=name, wall_s=wall, cpu_s=usage.ru_utime+usage.ru_stime,
                             maxrss_native=usage.ru_maxrss, sha256=digest))
summary = {name: {'median_wall_s': statistics.median(r['wall_s'] for r in rows if r['name']==name and r['iteration']>=0),
                  'median_cpu_s': statistics.median(r['cpu_s'] for r in rows if r['name']==name and r['iteration']>=0),
                  'maxrss_native': max(r['maxrss_native'] for r in rows if r['name']==name and r['iteration']>=0)} for name in bins}
report = dict(platform=platform.platform(), flags=flags, source_sha256={name:hashlib.sha256((root/(name+'.rs')).read_bytes()).hexdigest() for name in bins},
              runs=rows, summary=summary, rss_note='Linux KiB, macOS bytes; process RSS is not cgroup memory')
a.report.write_text(json.dumps(report, indent=2)+'\n')
print(json.dumps(summary, indent=2))
