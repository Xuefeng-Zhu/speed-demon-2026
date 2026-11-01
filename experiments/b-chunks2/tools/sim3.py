#!/usr/bin/env python3
"""Dynamic guided self-scheduling (claim a share of the remaining bytes) in the toy model."""
import sim, sim2

for n, np_ in ((8, 8), (12, 6), (20, 12)):
    m = int(max(1, -(-254 // (n * 16.78))))
    print(f'== n={n} ({np_} P) m={m}')
    for f in (1.0, 1.5, 2.0, 3.0):
        for k in (1.5, 2, 3, 4):
            pmax = 1 / (n * m)
            res = {s: sim.makespan_gss(sp, f, pmax / k, 0.0005, pmax) for s, sp in sim2.scen(n, np_)}
            cnt = res['uniform'][1]
            ms = {s: x[0] + sim2.ALPHA * x[1] for s, x in res.items()}
            het = [x for s, x in ms.items() if s != 'uniform']
            cnts = sorted({x[1] for x in res.values()})
            print(f'  f={f} pmin=base/{k}: chunks {cnts[0]}-{cnts[-1]} het mean {sum(het)/len(het):.3f} worst {max(het):.3f} uniform {ms["uniform"]:.3f}')
