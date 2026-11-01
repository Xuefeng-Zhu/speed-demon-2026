#!/usr/bin/env python3
"""series.py BIN THREADS: one run, RssAnon+RssShmem every ~300 us; prints a coarse series (ms, MB)."""
import os, subprocess, sys, time, shutil
b, t = sys.argv[1], sys.argv[2]
out = '/dev/shm/series-out'; shutil.rmtree(out, True)
env = dict(os.environ, SD_DATA='/projects/sandbox/.data/b-full', SD_OUT=out, SD_THREADS=t)
p = subprocess.Popen(['/projects/sandbox/.data/bin/' + b], env=env)
t0, s = time.perf_counter(), []
while p.poll() is None:
    try:
        v = {l.split(':')[0]: int(l.split()[1]) for l in open(f'/proc/{p.pid}/status') if l.startswith(('RssAnon', 'RssShmem'))}
        s.append(((time.perf_counter() - t0) * 1e3, (v['RssAnon'] + v['RssShmem']) / 1e3))
    except Exception:
        pass
pk = max(s, key=lambda x: x[1])
print(f'{b} t={t} peak {pk[1]:.1f} MB at {pk[0]:.0f} ms of {s[-1][0]:.0f}')
print(' '.join(f'{ms:.0f}:{mb:.0f}' for ms, mb in s[::max(1, len(s) // 40)]))
