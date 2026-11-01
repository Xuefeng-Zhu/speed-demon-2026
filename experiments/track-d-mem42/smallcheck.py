#!/usr/bin/env python3
"""smallcheck.py TRACK BIN [--threads T ...]

Runs BIN (name in /projects/sandbox/.data/bin or a path) on tiny and sample scale at seeds 2 and 7
(/projects/sandbox/.data/<t>-<scale>-s<seed>) and byte-compares with the official reference output
in <dir>-ref. Repeats for every --threads value (SD_THREADS; default unset). Exit 1 on mismatch."""
import argparse, os, shutil, subprocess, tempfile

D = '/projects/sandbox/.data'
OUT = {'a': 'summary.txt', 'b': 'results.txt', 'c': 'aggregates.txt', 'd': 'distances.txt'}

ap = argparse.ArgumentParser(description=__doc__)
ap.add_argument('track', choices=sorted(OUT))
ap.add_argument('bin')
ap.add_argument('--threads', action='append', default=[])
a = ap.parse_args()
b = os.path.abspath(a.bin) if '/' in a.bin else f'{D}/bin/{a.bin}'
bad = 0
for th in a.threads or [None]:
    for sc in ('tiny', 'sample'):
        for s in (2, 7):
            data = f'{D}/{a.track}-{sc}-s{s}'
            out = tempfile.mkdtemp(dir='/dev/shm')
            env = dict(os.environ, SD_DATA=data, SD_OUT=out)
            if th:
                env['SD_THREADS'] = th
            subprocess.run([b], env=env, check=True)
            ok = open(f'{out}/{OUT[a.track]}', 'rb').read() == open(f'{data}-ref/{OUT[a.track]}', 'rb').read()
            shutil.rmtree(out)
            bad += not ok
            print(f'{a.track} {sc} seed {s} threads {th or "-"}: {"ok" if ok else "MISMATCH"}')
raise SystemExit(1 if bad else 0)
