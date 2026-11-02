#!/usr/bin/env python3
"""kcheck.py TRACK BIN [-s SEEDS] [-t THREADS,...]: run BIN on every seed at every thread count
(0 = affinity default) and compare the output SHA-256 with expected.json. Exit 1 on any mismatch."""
import argparse, os, sys
sys.argv, argv = sys.argv[:1], sys.argv[1:]
import importlib.util
spec = importlib.util.spec_from_file_location('kb', os.path.join(os.path.dirname(os.path.abspath(__file__)), 'kbench.py'))
ap = argparse.ArgumentParser()
ap.add_argument('track')
ap.add_argument('bin')
ap.add_argument('-s', default='1,2')
ap.add_argument('-t', default='0,1,2,3,5,8,12,16')
ap.add_argument('--cpus', default='0-11')
a = ap.parse_args(argv)
src = open(spec.origin).read().replace('\nmain()\n', '\n')
kb = {}
exec(compile(src, spec.origin, 'exec'), kb)
bad = 0
for s in a.s.split(','):
    exp = kb['EXP'].get(f'{a.track}/{s}')
    for t in a.t.split(','):
        w, _, h = kb['run'](a.track, os.path.abspath(a.bin), int(s), False, int(t), a.cpus, check=False)
        ok = h == exp
        bad += not ok
        print(f'{a.track} seed {s} threads {t or "auto":>4}: {"OK " if ok else "BAD"} {h[:16]} {w:8.1f} ms' + ('' if exp else ' (no expected hash)'))
print('ALL OK' if not bad else f'{bad} MISMATCHES')
sys.exit(1 if bad else 0)
