#!/usr/bin/env python3
"""compare.py REPORT.json [...]: per memrun report, each binary's median wall, est M, paired wall
ratio against the first binary and the keep-rule break-even (M0/M1)^0.4 * (S0/S1)^0.3 with
M capped at 7.35 MB (Mref/50). S by binary name: 336 for the baseline, +1 for marking at every
refill (names with 'mark' or 'cand'), +2 for the mallopt call ('arena' or 'toppad'); cm-final
(the committed candidate) is 337."""
import json, statistics as st, sys

CAP = 7.35


def s_of(n):
    if n == 'cm-final':
        return 337
    return 336 + ('mark' in n or 'cand' in n) + 2 * ('arena' in n or 'toppad' in n)


for f in sys.argv[1:]:
    r = json.load(open(f))
    names = list(r['runs'])
    base = r['runs'][names[0]]
    m0 = max(CAP, st.median(x['est_M_mb'] for x in base))
    print(f'## {f} (reference {names[0]}, {len(base)} runs)')
    print('| binary | wall ms | est M MB | paired T1/T0 | break-even | passes |')
    print('|---|---|---|---|---|---|')
    for n in names:
        rs = r['runs'][n]
        m1 = max(CAP, st.median(x['est_M_mb'] for x in rs))
        ratio = st.median(y['wall_s'] / x['wall_s'] for x, y in zip(base, rs))
        be = (m0 / m1) ** 0.4 * (s_of(names[0]) / s_of(n)) ** 0.3
        ok = '-' if n == names[0] else 'yes' if ratio < be else 'no'
        print(f"| {n} | {st.median(x['wall_s'] for x in rs) * 1e3:.1f} | "
              f"{st.median(x['est_M_mb'] for x in rs):.2f} | {ratio:.3f} | {be:.3f} | {ok} |")
    print()
