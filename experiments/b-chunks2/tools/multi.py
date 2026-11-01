#!/usr/bin/env python3
"""Rounds of several Track B binaries under one emulation layout (local sandbox only).

    python3 multi.py --layout p20 --rounds 61 --report r.json base=/path/b c1=/path/c1 ...

The first binary is the base. Each round runs every binary once, in an order rotated by
one each round (one warmup round first); every run is checked against the seed-1 hash.
For each candidate the summary gives the median of the per-round wall ratio vs the base
(paired), a 95% bootstrap interval of that median, wins (rounds faster than the base),
median CPU ratio and median max RSS. Spinners of the layout run for the whole session.
"""
import argparse, json, os, pathlib, statistics as st, tempfile, time
import emu
from emu import boot


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--layout', required=True, choices=sorted(emu.LAYOUTS))
    p.add_argument('--rounds', type=int, default=21)
    p.add_argument('--report', required=True)
    p.add_argument('--data', default='/projects/sandbox/.data/speed-b-full')
    p.add_argument('bins', nargs='+', help='name=path, the first is the base')
    a = p.parse_args()
    bins = [b.split('=', 1) for b in a.bins]
    threads, cpus, spins, np_ = emu.LAYOUTS[a.layout]
    out = tempfile.mkdtemp(prefix='multi-', dir=os.environ.get('CH2', '/projects/sandbox/.data/ch2'))
    runs = {n: [] for n, _ in bins}
    sp = emu.spin(spins)
    try:
        time.sleep(0.3 if sp else 0)
        for i in range(-1, a.rounds):
            k = (i + 1) % len(bins)
            for n, b in bins[k:] + bins[:k]:
                r = emu.run_once(os.path.abspath(b), a.data, out, threads, cpus, np_)
                r['round'] = i
                r.pop('instr', None)
                if i >= 0:
                    runs[n].append(r)
    finally:
        for s in sp:
            s.kill()
            s.wait()
        for f in pathlib.Path(out).iterdir():
            f.unlink()
        os.rmdir(out)
    base = bins[0][0]
    summ = {}
    for n, _ in bins:
        rs, bs = runs[n], runs[base]
        d = {'wall_ms': 1e3 * st.median(r['wall_s'] for r in rs), 'cpu_ms': 1e3 * st.median(r['cpu_s'] for r in rs),
             'rss_kib': st.median(r['maxrss_kib'] for r in rs)}
        if n != base:
            dw = [x['wall_s'] / y['wall_s'] - 1 for x, y in zip(rs, bs)]
            dc = [x['cpu_s'] / y['cpu_s'] - 1 for x, y in zip(rs, bs)]
            lo, hi = boot(dw)
            d.update({'paired_wall_pct': 100 * st.median(dw), 'ci95_pct': [100 * lo, 100 * hi],
                      'wins': sum(x < 0 for x in dw), 'paired_cpu_pct': 100 * st.median(dc),
                      'rss_delta_kib': d['rss_kib'] - st.median(r['maxrss_kib'] for r in bs)})
        summ[n] = d
        print(f"{a.layout:8s} {n:8s} wall {d['wall_ms']:6.1f} cpu {d['cpu_ms']:6.0f} rss {d['rss_kib']:6.0f}"
              + (f" | paired {d['paired_wall_pct']:+.2f}% [{d['ci95_pct'][0]:+.2f}, {d['ci95_pct'][1]:+.2f}]"
                 f" wins {d['wins']}/{len(rs)} cpu {d['paired_cpu_pct']:+.2f}% rss {d['rss_delta_kib']:+.0f} KiB"
                 if n != base else ''), flush=True)
    rep = {'note': 'local sandbox measurements, not official scores', 'layout': a.layout, 'threads': threads,
           'cpus': cpus, 'spinners': spins, 'rounds': a.rounds,
           'binaries': {n: {'path': b, 'sha256': emu.R.sha256_file(b)} for n, b in bins},
           'summary': summ, 'runs': runs}
    pathlib.Path(a.report).write_text(json.dumps(rep, indent=1) + '\n')


if __name__ == '__main__':
    main()
