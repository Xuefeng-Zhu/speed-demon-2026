#!/usr/bin/env python3
"""Chunk-count sweep of an instrumented build with the test-only SD_NCHUNKS override.

    python3 sweep.py <binary> <layout> <rounds> <report.json> 16,24,32,...

Build the binary with: mkinst.py src.rs out.rs --nchunks-env, then build.sh out.rs <name>.
Rounds interleave the settings (one warmup round). Prints medians of wall, CPU, max RSS,
index and answer phase times and the index vCPU idle share per setting.
"""
import json, os, statistics as st, sys, tempfile
import emu

b, lay, n, rep, cs = sys.argv[1], sys.argv[2], int(sys.argv[3]), sys.argv[4], sys.argv[5].split(',')
threads, cpus, spins, np_ = emu.LAYOUTS[lay]
out = tempfile.mkdtemp(prefix='sw-', dir='/projects/sandbox/.data/ch2')
sp = emu.spin(spins)
res = {c: [] for c in cs}
try:
    for i in range(-1, n):
        for c in cs:
            r = emu.run_once(os.path.abspath(b), '/projects/sandbox/.data/speed-b-full', out, threads, cpus, np_, {'SD_NCHUNKS': c})
            if i >= 0:
                res[c].append(r)
finally:
    for s in sp:
        s.kill(); s.wait()
summ = {}
for c, rs in res.items():
    m = lambda f: st.median(f(r) for r in rs)
    summ[c] = {'wall_ms': m(lambda r: r['wall_s'] * 1e3), 'cpu_ms': m(lambda r: r['cpu_s'] * 1e3),
               'rss_kib': m(lambda r: r['maxrss_kib']), 'index_ms': m(lambda r: r['tail']['index_ms']),
               'answer_ms': m(lambda r: r['tail']['answer_ms']), 'cpu_idle': m(lambda r: r['tail']['cpu_idle_frac'])}
    print(lay, c, {k: round(v, 3) for k, v in summ[c].items()}, flush=True)
json.dump({'note': 'local sandbox measurements, not official scores', 'layout': lay, 'summary': summ,
           'runs': {c: [{k: r[k] for k in ('wall_s', 'cpu_s', 'maxrss_kib', 'tail')} for r in rs] for c, rs in res.items()}},
          open(rep, 'w'), indent=1)
