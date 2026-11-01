#!/usr/bin/env python3
"""Toy model of the index phase: chunks claimed in order by the first free thread.

Work is normalized so that the whole file takes 1.0 time units on one speed-1 thread.
A chunk of fraction f of the bytes takes (f + c0) / speed. Reports the makespan
relative to the ideal 1 / sum(speeds) (1.00 = no tail). Used only to pick candidate
formulas before measuring them; it ignores memory bandwidth, SMT and the answer phase.
"""
import heapq


def makespan(sizes, speeds, c0=0.0):
    free = [(0.0, i) for i in range(len(speeds))]
    heapq.heapify(free)
    for f in sizes:
        t, i = heapq.heappop(free)
        heapq.heappush(free, (t + (f + c0) / speeds[i], i))
    return max(t for t, _ in free) * sum(speeds)


def frac_from_cuts(g, c):
    """Chunk fractions from a cut function g(k) on 0..c, g(0) = 0, g(c) = 1."""
    return [g(k + 1) - g(k) for k in range(c)]


def layouts(n, m):
    """Candidate chunkings for n threads, m = the baseline's rounds (chunks <= 16 MiB)."""
    out = {'base n*m equal': [1 / (n * m)] * (n * m)}
    for c in (n * m, n * m + n // 2, 2 * n * m, n * m + n):
        for p in (1.5, 2.0):
            out[f'pow{p} C={c}'] = frac_from_cuts(lambda k: 1 - (1 - k / c) ** p, c)
    # rounds: m rounds of n equal chunks plus a tail round of n chunks taking share q
    for q in (0.1, 0.15, 0.2, 0.25):
        out[f'm rounds + tail round {q}'] = [(1 - q) / (n * m)] * (n * m) + [q / n] * n
    return out


SCEN = {
    'u8': [1.0] * 8,
    'u12': [1.0] * 12,
    'u20': [1.0] * 20,
    '20: 12P + 8E@0.5': [1.0] * 12 + [0.5] * 8,
    '20: 12P + 8E@0.67': [1.0] * 12 + [0.67] * 8,
    '12: 6P + 6E@0.4': [1.0] * 6 + [0.4] * 6,
    '12: 6P + 6E@0.67': [1.0] * 6 + [0.67] * 6,
}

if __name__ == '__main__':
    for name, sp in SCEN.items():
        n = len(sp)
        m = -(-254 // (n * 16.78))  # 254 MB file, 16 MiB per chunk
        m = int(max(1, m))
        print(f'== {name} (m={m})')
        for k, v in layouts(n, m).items():
            print(f'  {k:28s} chunks {len(v):3d} max {max(v)*254:5.1f} MB  makespan {makespan(v, sp, 0.0005):.3f}')


def makespan_gss(speeds, f, pmin, c0=0.0, pmax=1.0):
    """Dynamic: each claim takes min(pmax, max(pmin, remaining / (f * n))) of the bytes.
    Returns (normalized makespan, number of chunks)."""
    n = len(speeds)
    free = [(0.0, i) for i in range(n)]
    heapq.heapify(free)
    rem, cnt = 1.0, 0
    while rem > 1e-12:
        p = min(rem, pmax, max(pmin, rem / (f * n)))
        if rem - p < pmin / 4:
            p = rem
        rem -= p
        cnt += 1
        t, i = heapq.heappop(free)
        heapq.heappush(free, (t + (p + c0) / speeds[i], i))
    return max(t for t, _ in free) * sum(speeds), cnt
