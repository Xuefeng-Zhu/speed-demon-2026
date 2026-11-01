#!/usr/bin/env python3
"""order_test.py --binary BIN [--data DIR] [--threads 1,3,8,20] [--tmp DIR]

Copy of experiments/a-mem/order_test.py (branch a-mem) with one addition: --tmp picks the
file system the outputs are written to. The default /dev/shm is tmpfs, which refuses O_DIRECT,
so it tests the buffered fallback of the output writer; a directory on a disk file system
(ext4, xfs) tests the O_DIRECT path.

Checks the early hour closing and its fallback (start over without closing hours early when a
record comes for a closed hour) against the official reference on reordered copies of a sample
log (default /projects/sandbox/.data/a-sample-s2, about 46 chunks of 512 KiB):

  original        file order of the generator (hours close early, no fallback expected)
  sorted          lines sorted by timestamp
  shuffled        lines in random order (fallback)
  first-to-end    a line of hour 0 moved to the end (fallback)
  last-to-start   a line of hour 71 moved to the start (closes hours too early, fallback)
  one-hour-late   a copy of a line of each hour h after the first line of hour h + 1 (allowed)
  two-hours-late  a copy of a line of hour 30 about 2 MB after the first line of hour 32, so in
                  a later chunk than that line (fallback, unless the chunks between finish
                  together, as with many threads, so hour 30 is not closed by then)
  empty           no lines

Every variant runs at each thread count and must match the reference byte for byte. The
binary's stderr is shown after the verdict (a profiling build may report the fallback there)."""
import argparse, collections, importlib.util, os, random, subprocess, sys, tempfile

ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
ap.add_argument('--binary', required=True)
ap.add_argument('--data', default='/projects/sandbox/.data/a-sample-s2')
ap.add_argument('--threads', default='1,3,8,20')
ap.add_argument('--tmp', default='/dev/shm')
a = ap.parse_args()
root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
spec = importlib.util.spec_from_file_location('ref', os.path.join(root, 'official/reference/a_ingest.py'))
ref = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ref)

lines = open(os.path.join(a.data, 'requests.log'), 'rb').read().splitlines(keepends=True)


def hour(line):
    day = {b'30': 0, b'31': 1, b'01': 2, b'02': 3}[line[8:10]]
    return day * 24 + int(line[11:13]) - 18


def move(ls, i, j):
    """Moves line i to just after line j (j > i)."""
    ls = ls[:]
    ls.insert(j, ls.pop(i))
    return ls


first = {}
for i, l in enumerate(lines):
    first.setdefault(hour(l), i)
rng = random.Random(4)
variants = collections.OrderedDict()
variants['original'] = lines
variants['sorted'] = sorted(lines, key=lambda l: l[:27])
variants['shuffled'] = rng.sample(lines, len(lines))
variants['first-to-end'] = move(lines, first[0], len(lines) - 1)
variants['last-to-start'] = [lines[first[71]]] + lines[:first[71]] + lines[first[71] + 1:]
late = lines[:]
for h in range(70, -1, -1):
    late.insert(first[h + 1] + 1, lines[first[h]])
variants['one-hour-late'] = late
at = first[32] + 1 + 2_000_000 // 80  # lines are about 80 bytes
variants['two-hours-late'] = lines[:at] + [lines[first[30]]] + lines[at:]
variants['empty'] = []

bad = 0
with tempfile.TemporaryDirectory(dir=a.tmp) as t:
    for name, ls in variants.items():
        data, want, got = (os.path.join(t, x) for x in ('data', 'want', 'got'))
        for d in (data, want, got):
            os.makedirs(d, exist_ok=True)
        with open(os.path.join(data, 'requests.log'), 'wb') as f:
            f.writelines(ls)
        ref.main(data, want)
        expect = open(os.path.join(want, 'summary.txt'), 'rb').read()
        for th in a.threads.split(','):
            env = dict(os.environ, SD_DATA=data, SD_OUT=got, SD_THREADS=th)
            err = subprocess.run([a.binary], env=env, check=True, capture_output=True).stderr
            ok = open(os.path.join(got, 'summary.txt'), 'rb').read() == expect
            bad += not ok
            print(f'{name:15s} threads {th:>2s}: {"ok" if ok else "MISMATCH"} {err.decode().strip()}')
sys.exit(1 if bad else 0)
