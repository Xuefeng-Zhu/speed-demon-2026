#!/usr/bin/env python3
"""MODEL, not a measurement. Lockstep model of the index-phase anonymous memory (MB) for chunk schedules,
with sizes from the baseline INFO lines (seed 1). Usage: sim.py [base_MB].
Every thread scans at the same speed; chunks are claimed in index order by the first free thread.
A chunk's stream grows while it is scanned, then during its CSR the stream, the docs array and
offs (+ end) are live; after it the stream (and end) are freed and unmapped (no allocator retention).
Rows are touched in proportion to the bytes scanned. Base = structures live through the scan."""
import sys

L = 253.8           # corpus MB
SIG = 23.2 / L      # stream MB per corpus MB
DEL = 22.7 / L      # docs MB per corpus MB
ROWS = 10.85
OFFS = 0.212        # MB per chunk
CSR = 0.10          # CSR time per scan time
CSR0 = 0.3          # fixed CSR ms
V = 254 / 1300.0    # corpus MB per ms per thread (about 1300 ms of summed scan)


def run(bounds, nt, base, end=True):
    sizes = [b - a for a, b in zip(bounds, bounds[1:])]
    n = len(sizes)
    free_at = [0.0] * nt
    ev = []  # (t0, t_scan_end, t_csr_end, size)
    for k, s in enumerate(sizes):
        th = min(range(nt), key=lambda i: free_at[i])
        t0 = free_at[th]
        t1 = t0 + s / V
        t2 = t1 + CSR * s / V + CSR0
        free_at[th] = t2
        ev.append((t0, t1, t2, s))
    end_t = max(free_at)
    times = sorted({x for e in ev for x in e[:3]} | {end_t})
    # sample finely
    import itertools
    pts = []
    t = 0.0
    while t <= end_t + 1e-9:
        pts.append(t)
        t += end_t / 4000
    pts += [x - 1e-6 for x in times] + times
    best = (0, 0)
    for t in pts:
        m = base
        scanned = 0.0
        for (t0, t1, t2, s) in ev:
            if t < t0:
                continue
            if t < t1:   # scanning: stream grows
                f = (t - t0) / (t1 - t0)
                m += SIG * s * f
                scanned += s * f
            elif t < t2:  # CSR: stream + docs + offs (+ end)
                m += SIG * s + DEL * s + OFFS * (2 if end else 1)
                scanned += s
            else:
                m += DEL * s + OFFS
                scanned += s
        m += ROWS * scanned / L
        if m > best[0]:
            best = (m, t)
    return best[0], best[1], end_t, max(free_at) - min(free_at)


def equal(n):
    return [L * k / n for k in range(n + 1)]


def rounds(nt, fr):
    """len(fr) rounds of nt equal chunks; round r covers fraction fr[r] of the corpus."""
    b, x = [0.0], 0.0
    for f in fr:
        for _ in range(nt):
            x += f * L / nt
            b.append(x)
    b[-1] = L
    return b


def guided(n, p=2.0):
    return [L * (1 - (1 - k / n) ** p) for k in range(n + 1)]


if __name__ == '__main__':
    base = float(sys.argv[1]) if len(sys.argv) > 1 else 7.4
    for nt in (8, 12):
        print(f'--- {nt} threads, base {base} MB')
        cases = [('equal 2/thread', equal(2 * nt)), ('equal 3/thread', equal(3 * nt)),
                 ('equal 4/thread', equal(4 * nt))]
        for a in (0.6, 0.65, 0.7, 0.74, 0.78):
            cases.append((f'2 rounds {a:.2f}/{1 - a:.2f}', rounds(nt, [a, 1 - a])))
        for fr in ([0.55, 0.3, 0.15], [0.6, 0.27, 0.13], [0.5, 0.33, 0.17]):
            cases.append((f'3 rounds {fr}', rounds(nt, fr)))
        for p in (1.5, 2.0, 2.5):
            cases.append((f'guided p={p} 2/thread', guided(2 * nt, p)))
            cases.append((f'guided p={p} 3/thread', guided(3 * nt, p)))
        for name, b in cases:
            for end in (True, False):
                pk, at, tend, tail = run(b, nt, base, end)
                print(f'{name:34s} end={int(end)} peak {pk:5.1f} MB at {at:6.1f} of {tend:6.1f} ms, tail {tail:4.1f} ms, '
                      f'max chunk {max(y - x for x, y in zip(b, b[1:])):.1f} MB')
