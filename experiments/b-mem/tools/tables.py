#!/usr/bin/env python3
"""tables.py <reports dir>: Markdown tables from the run.py and memrun.py reports of experiments/b-mem."""
import glob, json, os, statistics as st, sys

R = sys.argv[1] if len(sys.argv) > 1 else 'reports'


def pair(path):
    d = json.load(open(path))
    c = [r for r in d['runs'] if not r.get('warmup')]
    b = [r for r in d['baseline_runs'] if not r.get('warmup')]
    n = min(len(c), len(b))
    dw = [c[i]['wall_s'] / b[i]['wall_s'] - 1 for i in range(n)]
    dc = [c[i]['cpu_s'] / b[i]['cpu_s'] - 1 for i in range(n)]
    dr = [c[i]['maxrss_kib'] / b[i]['maxrss_kib'] - 1 for i in range(n)]
    return dict(n=n, cw=st.median(r['wall_s'] for r in c) * 1e3, bw=st.median(r['wall_s'] for r in b) * 1e3,
                pw=st.median(dw) * 100, wins=sum(x < 0 for x in dw), pc=st.median(dc) * 100,
                cr=st.median(r['maxrss_kib'] for r in c), br=st.median(r['maxrss_kib'] for r in b),
                pr=st.median(dr) * 100, ccpu=st.median(r['cpu_s'] for r in c), bcpu=st.median(r['cpu_s'] for r in b),
                threads=c[0]['threads'], csha=d['environment']['binary_sha256'][:12], bsha=d['baseline_binary_sha256'][:12])


def row(name, p):
    return (f"| `{name}` | {p['threads']} | {p['n']} | {p['cw']:.1f} | {p['bw']:.1f} | {p['pw']:+.2f}% | {p['wins']}/{p['n']} "
            f"| {p['pc']:+.2f}% | {p['cr']:,.0f} / {p['br']:,.0f} | {p['pr']:+.1f}% |")


HDR = ('| Report | Threads | Pairs | Cand wall ms | Base wall ms | Paired wall | Wins | Paired CPU | Max RSS cand / base KiB | Paired RSS |\n'
       '| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |')
for group in ('final-*', 'screen-*', 'loo21-*', 'loo-*'):
    files = sorted(glob.glob(f'{R}/{group}.json'), key=lambda f: (f.split('-t')[0], int(f.rsplit('-t', 1)[1][:-5])))
    if not files:
        continue
    print(f'\n### {group}\n')
    print(HDR)
    for f in files:
        print(row(os.path.basename(f), pair(f)))
    p = pair(files[0])
    print(f"\n(candidate binary {p['csha']}..., baseline binary {p['bsha']}...)")

print('\n### instrumented memory reports (memrun.py), medians\n')
for f in sorted(glob.glob(f'{R}/mem/*.json')):
    d = json.load(open(f))
    for b, s in d['summary'].items():
        print(f"{os.path.basename(f):34s} {b:16s} t={d['threads']} env={d['env']} runs={d['runs_per_binary']} "
              f"maxrss {s['maxrss_kib_median']:.0f} [{s['maxrss_kib_min']}..{s['maxrss_kib_max']}] KiB")
