#!/usr/bin/env python3
"""hwm.py <runs> <threads> <bin> [bin ...] [-- KEY=VAL ...]: alternate instrumented binaries,
report the median VmHWM (kB, MEM write line) and median RssAnon at the index/answer ends."""
import os, subprocess, sys, statistics as st, tempfile, shutil
D = '/projects/sandbox/.data'
args = sys.argv[1:]
extra = {}
if '--' in args:
    i = args.index('--')
    extra = dict(kv.split('=', 1) for kv in args[i + 1:])
    args = args[:i]
n, t, bins = int(args[0]), args[1], args[2:]
res = {b: [] for b in bins}
for _ in range(n):
    for b in bins:
        o = tempfile.mkdtemp(dir=D + '/mem')
        env = dict(os.environ, SD_DATA=D + '/speed-b-full', SD_OUT=o, SD_THREADS=t, **extra)
        p = subprocess.run([D + '/bin/' + b], env=env, capture_output=True, text=True)
        shutil.rmtree(o)
        m = {}
        for l in p.stderr.splitlines():
            x = l.split()
            if x and x[0] == 'MEM':
                m[x[1]] = [int(v) for v in x[2:]]
        res[b].append((m['write'][0], m['index'][2], m['answer'][2], m['write'][3]))
for b in bins:
    r = res[b]
    print(f'{b:20s} t={t} {extra} VmHWM med {st.median(x[0] for x in r):.0f} '
          f'[{min(x[0] for x in r)}..{max(x[0] for x in r)}] anon@index {st.median(x[1] for x in r):.0f} '
          f'anon@answer {st.median(x[2] for x in r):.0f} file@end {st.median(x[3] for x in r):.0f}')
