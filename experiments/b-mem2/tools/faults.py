#!/usr/bin/env python3
"""faults.py THREADS BIN...: minor faults, wall and ru_maxrss of one run per binary (os.wait4)."""
import os, subprocess, sys, time, shutil
for b in sys.argv[2:]:
    out = '/dev/shm/faults-out'; shutil.rmtree(out, True)
    env = dict(os.environ, SD_DATA='/projects/sandbox/.data/b-full', SD_OUT=out, SD_THREADS=sys.argv[1])
    t0 = time.perf_counter()
    p = subprocess.Popen(['/projects/sandbox/.data/bin/' + b], env=env)
    _, _, ru = os.wait4(p.pid, 0)
    print(f'{b:18} t={sys.argv[1]} minflt {ru.ru_minflt:7} wall {(time.perf_counter() - t0) * 1e3:6.1f} ms maxrss {ru.ru_maxrss} KiB')
