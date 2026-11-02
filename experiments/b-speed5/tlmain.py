#!/usr/bin/env python3
"""tlmain.py binary [runs]: median main-thread time, user, sys and faults between consecutive main-thread events."""
import os, statistics, subprocess, sys, time
K = os.path.expanduser('~/kiro-b')
b = sys.argv[1] if '/' in sys.argv[1] else f'{K}/bin/{sys.argv[1]}'
n = int(sys.argv[2]) if len(sys.argv) > 2 else 7
rows = {}
order = []
for r in range(n + 1):
    env = dict(os.environ, SD_DATA=f'{K}/data/s1', SD_OUT='/dev/shm/kb-tlm', KB_T0=str(time.clock_gettime_ns(time.CLOCK_MONOTONIC)))
    os.makedirs('/dev/shm/kb-tlm', exist_ok=True)
    p = subprocess.run(['taskset', '-c', '0-11', b], env=env, capture_output=True, text=True)
    ev = [l.split() for l in p.stderr.splitlines() if l.startswith('EV ') and l.split()[2] == '99']
    if r == 0:
        continue  # warm-up
    prev = None
    for e in ev:
        lab, t, u, s, f = e[1], int(e[4]) / 1e6, int(e[5]) / 1e3, int(e[6]) / 1e3, int(e[7])
        if prev:
            key = f'{prev[0]} -> {lab}'
            if key not in rows:
                rows[key] = []; order.append(key)
            rows[key].append((t - prev[1], u - prev[2], s - prev[3], f - prev[4]))
        prev = (lab, t, u, s, f)
print(f'{os.path.basename(b)}: median of {n} runs (ms wall, ms user, ms sys, minor faults)')
for k in order:
    v = rows[k]
    print(f'  {k:28s} {statistics.median(x[0] for x in v):6.2f}  {statistics.median(x[1] for x in v):6.2f}  {statistics.median(x[2] for x in v):6.2f}  {statistics.median(x[3] for x in v):6.0f}')
