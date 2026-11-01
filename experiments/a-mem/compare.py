#!/usr/bin/env python3
"""compare.py BASE CAND REPORT.json [...] [--s0 414 --s1 468]

For memrun.py reports (interleaved runs, same index = one pair): paired median wall ratio
CAND/BASE and wins, median live M and est M of both, and the keep rule
T1/T0 < (M0/M1)^0.4 * (S0/S1)^0.3 (M capped below at Mref/50 = 4.56 MB for Track A), with the
predicted K ratio (T0/T1)^0.5 * (M0/M1)^0.2 * (S0/S1)^0.15. Local sandbox numbers, not board
results."""
import argparse, json, statistics as st

ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
ap.add_argument('base')
ap.add_argument('cand')
ap.add_argument('reports', nargs='+')
ap.add_argument('--s0', type=float, default=414)
ap.add_argument('--s1', type=float, default=468)
a = ap.parse_args()
CAP = 4.56
print('| Threads | T base / cand (ms) | paired T1/T0 (wins) | live M base / cand (MB) | est M base / cand (MB) '
      '| break-even T1/T0 (live M) | predicted K (live M) |')
print('|---:|---|---|---|---|---:|---:|')
for path in a.reports:
    r = json.load(open(path))
    b, c = r['runs'][a.base], r['runs'][a.cand]
    ratios = [y['wall_s'] / x['wall_s'] for x, y in zip(b, c)]
    t = st.median(ratios)
    wins = sum(q < 1 for q in ratios)
    tb, tc = (st.median(x['wall_s'] for x in rs) * 1e3 for rs in (b, c))
    lb, lc = (max(CAP, st.median(x['live_M_mb'] for x in rs)) for rs in (b, c))
    eb, ec = (max(CAP, st.median(x['est_M_mb'] for x in rs)) for rs in (b, c))
    even = (lb / lc) ** 0.4 * (a.s0 / a.s1) ** 0.3
    k = (1 / t) ** 0.5 * (lb / lc) ** 0.2 * (a.s0 / a.s1) ** 0.15
    print(f"| {r['threads'] or 'default'} | {tb:.1f} / {tc:.1f} | {t:.4f} ({wins}/{len(ratios)}) | {lb:.2f} / {lc:.2f} "
          f"| {eb:.2f} / {ec:.2f} | {even:.4f} | {k:.4f} |")
