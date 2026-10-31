#!/usr/bin/env python3
"""Paired deltas from run.py reports: python3 pair.py report.json [...]"""
import json, statistics as st, sys
for p in sys.argv[1:]:
    d = json.load(open(p))
    c = [r for r in d['runs'] if not r.get('warmup')]
    b = [r for r in d['baseline_runs'] if not r.get('warmup')]
    n = min(len(c), len(b))
    dw = [c[i]['wall_s'] / b[i]['wall_s'] - 1 for i in range(n)]
    dc = [c[i]['cpu_s'] / b[i]['cpu_s'] - 1 for i in range(n)]
    wins = sum(x < 0 for x in dw)
    mc, mb = st.median(r['wall_s'] for r in c), st.median(r['wall_s'] for r in b)
    rc, rb = st.median(r['maxrss_kib'] for r in c), st.median(r['maxrss_kib'] for r in b)
    print(f"{p.split('/')[-1]:34s} n={n} wall cand {mc*1e3:.1f} base {mb*1e3:.1f} ms | paired wall {st.median(dw)*100:+.2f}% "
          f"(wins {wins}/{n}) cpu {st.median(dc)*100:+.2f}% | rss {rc} vs {rb} KiB")
