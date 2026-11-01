#!/usr/bin/env python3
"""Row-index fallback check for Track D: graphs with hub nodes whose rows hold
256 or more edges (so a byte offset per row cannot span a block and the packed
row index falls back to smaller blocks, down to one row per block), plus
blocks whose total span is just under or over 255. Every answer is compared
with an independent Python Dijkstra.

Usage: hubs.py BINARY...
"""
import heapq, random, subprocess, sys, tempfile
from pathlib import Path

rng = random.Random(42042)


def dijkstra(n, adj, s):
    d = [None] * n
    d[s] = 0
    pq = [(0, s)]
    while pq:
        du, u = heapq.heappop(pq)
        if du > d[u]:
            continue
        for v, w in adj[u]:
            if d[v] is None or du + w < d[v]:
                d[v] = du + w
                heapq.heappush(pq, (du + w, v))
    return d


total = 0
with tempfile.TemporaryDirectory(prefix='d-hubs42-') as tmp:
    data, out = Path(tmp, 'data'), Path(tmp, 'out')
    data.mkdir(); out.mkdir()
    for case in range(24):
        n = rng.choice([300, 700, 2000, 5000])
        edges = []
        hubs = rng.sample(range(n), rng.choice([1, 2, 5]))
        for h in hubs:
            deg = rng.choice([255, 256, 257, 600, n - 1])
            for v in rng.sample(range(n), min(deg, n)):
                edges.append((h, v, rng.choice([0, 1, 7, 2047, 2048, rng.randrange(1 << 32)])))
                if rng.randrange(3) == 0:
                    edges.append((v, h, rng.randrange(5000)))
        # Blocks whose rows add up to about 255 edges.
        for u in range(0, n, 64):
            budget = rng.choice([250, 254, 255, 256, 300])
            for k in range(budget):
                a = u + rng.randrange(min(64, n - u))
                edges.append((a, rng.randrange(n), rng.randrange(3000)))
        for _ in range(n):
            edges.append((rng.randrange(n), rng.randrange(n), rng.randrange(1 << 12)))
        rng.shuffle(edges)
        qs = [(rng.choice(hubs + [rng.randrange(n)]), rng.randrange(n)) for _ in range(60)]
        Path(data, 'graph.txt').write_text(f'{n} {len(edges)}\n' + ''.join(f'{u} {v} {w}\n' for u, v, w in edges))
        Path(data, 'queries.txt').write_text(''.join(f'{s} {t}\n' for s, t in qs))
        adj = [[] for _ in range(n)]
        for u, v, w in edges:
            adj[u].append((v, w))
        cache = {}
        want = []
        for s, t in qs:
            if s not in cache:
                cache[s] = dijkstra(n, adj, s)
            d = cache[s][t]
            want.append(f'{-1 if d is None else d}\n')
        for b in sys.argv[1:]:
            subprocess.run([b], env={'SD_DATA': str(data), 'SD_OUT': str(out)}, check=True)
            got = Path(out, 'distances.txt').read_text()
            if got != ''.join(want):
                sys.exit(f'FAIL {b} case {case} n={n}')
        total += len(qs)
print(f'PASS 24 hub graphs, {total} queries per binary')
