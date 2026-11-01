#!/usr/bin/env python3
"""Robustness of chunk shapes over E/P speed ratios in the toy model of sim.py, plus a
per-chunk answer-phase cost alpha (in units of the index work, measured: about 0.002)."""
import sim

ALPHA = 0.002


def shapes(n, m):
    c0 = n * m
    out = {'base': [1 / c0] * c0}
    for extra in (n // 2, n):
        c = c0 + extra
        out[f'eq C={c}'] = [1 / c] * c
        for p in (1.25, 1.5, 2.0):
            out[f'pow{p} C={c}'] = sim.frac_from_cuts(lambda k: 1 - (1 - k / c) ** p, c)
        for q in (0.15, 0.2, 0.25, 0.3):
            out[f'tail{q} C={c}'] = [(1 - q) / c0] * c0 + [q / extra] * extra
            # tail round with linearly decreasing sizes
            w = [extra - i for i in range(extra)]
            out[f'taillin{q} C={c}'] = [(1 - q) / c0] * c0 + [q * x / sum(w) for x in w]
    return out


def scen(n, np_):
    yield 'uniform', [1.0] * n
    for r in (0.4, 0.5, 0.6, 0.67, 0.75, 0.85):
        yield f'{r}', [1.0] * np_ + [r] * (n - np_)


for n, np_ in ((8, 8), (12, 6), (20, 12)):
    m = max(1, -(-254 // (n * 16.78)))
    m = int(m)
    print(f'== n={n} ({np_} P) m={m}')
    rows = []
    for k, v in shapes(n, m).items():
        ms = {s: sim.makespan(v, sp, 0.0005) + ALPHA * len(v) for s, sp in scen(n, np_)}
        het = [x for s, x in ms.items() if s != 'uniform']
        rows.append((sum(het) / len(het), max(het), ms['uniform'], k, len(v), max(v) * 254))
    base = [r for r in rows if r[3] == 'base'][0]
    rows.sort()
    for r in [base] + rows[:12]:
        print(f'  {r[3]:22s} C={r[4]:3d} maxMB {r[5]:5.1f} het mean {r[0]:.3f} worst {r[1]:.3f} uniform {r[2]:.3f}')
