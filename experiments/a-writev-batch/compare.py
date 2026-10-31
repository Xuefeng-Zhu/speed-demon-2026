#!/usr/bin/env python3
"""Randomized native paired A comparison; wall/RSS are not official scores."""
import argparse, hashlib, json, os, pathlib, platform, random, statistics, subprocess, tempfile, time

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--data', required=True, type=pathlib.Path)
p.add_argument('--report', required=True, type=pathlib.Path)
p.add_argument('--threads', type=int, default=12)
p.add_argument('--runs', type=int, default=15)
p.add_argument('--seed', type=int, default=88411)
a = p.parse_args()
if a.runs < 1 or a.threads < 1:
    p.error('runs and threads must be positive')
here = pathlib.Path(__file__).resolve().parent
data = a.data.resolve()
expected = '495ca09682b9673ef836a506496177680bb4a3af54255174befddb1f83481cd3'
rng = random.Random(a.seed)
records = {key: [] for key in ('baseline', 'candidate')}
with tempfile.TemporaryDirectory(prefix='sd-a-writev-compare-') as tmp:
    t = pathlib.Path(tmp)
    out = t / 'out'; out.mkdir()
    for key in records:
        text = (here / (key + '.rs')).read_text()
        if platform.system() == 'Darwin':
            old = 'let (read, private, fixed, anon, null) = (1, 2, 0x10, 0x20, std::ptr::null_mut());'
            assert text.count(old) == 1
            text = text.replace(old, 'let (read, private, fixed, anon, null) = (1, 2, 0x10, 0x1000, std::ptr::null_mut());')
        source = t / (key + '.rs'); source.write_text(text)
        flags = ['rustc', '--edition=2021', '-O', '-C', 'lto=fat', '-C', 'codegen-units=1', '-C', 'panic=abort']
        if platform.machine().lower() in ('x86_64', 'amd64'):
            flags += ['-C', 'target-cpu=x86-64-v3']
        subprocess.run(flags + [str(source), '-o', str(t / key)], check=True)
    for i in range(a.runs + 1):
        order = list(records); rng.shuffle(order)
        for key in order:
            env = dict(os.environ, SD_DATA=str(data), SD_OUT=str(out), SD_THREADS=str(a.threads))
            start = time.perf_counter()
            proc = subprocess.Popen([str(t / key)], env=env, stdout=subprocess.DEVNULL)
            _, status, use = os.wait4(proc.pid, 0)
            elapsed = time.perf_counter() - start
            if os.waitstatus_to_exitcode(status):
                raise SystemExit(f'{key}: nonzero exit')
            digest = hashlib.sha256((out / 'summary.txt').read_bytes()).hexdigest()
            if digest != expected:
                raise SystemExit(f'{key}: hash mismatch {digest}')
            if i:
                records[key].append({'wall_s': elapsed, 'cpu_s': use.ru_utime + use.ru_stime,
                                     'ru_maxrss': use.ru_maxrss, 'sha256': digest})
report = {'note': 'Native timings include startup; ru_maxrss is bytes on Darwin and KiB on Linux, not cgroup.',
          'platform': platform.platform(), 'rustc': subprocess.check_output(['rustc', '--version'], text=True).strip(),
          'source_sha256': {k: hashlib.sha256((here / (k + '.rs')).read_bytes()).hexdigest() for k in records},
          'threads': a.threads, 'seed': a.seed, 'runs': records,
          'medians': {k: {f: statistics.median(v[f] for v in rows) for f in ('wall_s', 'cpu_s', 'ru_maxrss')}
                      for k, rows in records.items()}}
a.report.write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps(report['medians'], indent=2))
