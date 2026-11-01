"""Summarise bench.sh output as paired differences: `python3 paired.py report.txt`."""
import collections
import re
import statistics as st
import sys

HASH = 'a23dbdf0a3e4'  # first 12 hex digits of the published full seed-1 SHA-256
runs = collections.defaultdict(dict)
for line in open(sys.argv[1]):
    m = re.match(r'(\S+) th=(\d+) r=(\d+)\s+(.*)', line)
    if not m:
        continue
    rest = m.group(4)
    mark = {k: float(t) for t, k in re.findall(r'([\d.]+) ms (\w+) cur', rest)}
    w = re.search(r'wall_us (\d+) peak (\d+) thp (-?\d+)', rest)
    runs[(int(m.group(2)), int(m.group(3)))][m.group(1)] = {
        'relabel window': mark['relabel'] - mark['renumber'],
        'start to queries done': mark['queries'],
        'container wall': int(w.group(1)) / 1e3,
        'cgroup peak (MB)': int(w.group(2)) / 1e6,
        'THP faults': int(w.group(3)),
        'ok': HASH in rest,
    }
for th in sorted({k[0] for k in runs}):
    pairs = [v for k, v in sorted(runs.items()) if k[0] == th and len(v) == 2]
    ok = all(p[x]['ok'] for p in pairs for x in p)
    print(f'{th} threads: {len(pairs)} pairs, every output hash matches: {ok}')
    for key in ['relabel window', 'start to queries done', 'container wall', 'cgroup peak (MB)', 'THP faults']:
        b = [p['baseline'][key] for p in pairs]
        c = [p['candidate'][key] for p in pairs]
        d = [y - x for x, y in zip(b, c)]
        print(f'  {key:<22} baseline {st.median(b):8.2f}  candidate {st.median(c):8.2f}  '
              f'paired median {st.median(d):+7.2f}  candidate lower in {sum(x < 0 for x in d)}/{len(d)}')
