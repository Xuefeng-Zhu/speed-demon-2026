#!/usr/bin/env python3
"""Exercise compact/wide radix transitions against independent Dijkstra."""
import heapq
import os
from pathlib import Path
import subprocess
import sys
import tempfile

# The long directed chain crosses 2^43 in both directions. Parallel edges,
# zero edges, self-loops, and detours create stale entries around the cutoff.
n = 6400
road_n = 4200
maxw = (1 << 32) - 1
edges = []
for u in range(road_n - 1):
    edges.extend(((u, u + 1, maxw), (u + 1, u, maxw - (u % 29))))
    if u % 71 == 0:
        edges.append((u, u + 1, maxw - 7))
    if u % 97 == 0:
        edges.append((u, u, 0))
for u in (1, 99, 800, 1900, 2047, 2048, 2099, 3000):
    edges.extend(((u, u + 2, maxw), (u, u + 2, maxw - 1), (u + 2, u, maxw)))
base = road_n
for u in range(base, base + 2048):
    edges.append((u, u + 1, maxw))
for delta in (-1, 0, 1):
    edges.append((base + 2048, base + 2050 + delta, 2048 + delta))
adj = [[] for _ in range(n)]
for u, v, w in edges:
    adj[u].append((v, w))
queries = [(0, x) for x in (1, 2047, 2048, 2049, 2050, 3000, 4199)]
queries += [(4199, x) for x in (0, 100, 2000, 2150, 2151, 2152, 4199)]
queries += [(3, 2099), (2099, 3), (800, 3000), (3000, 800)]
queries += [(base, base + 2050 + delta) for delta in (-1, 0, 1)]
def shortest(start, goal):
    d = [None] * n
    d[start] = 0
    heap = [(0, start)]
    while heap:
        cost, u = heapq.heappop(heap)
        if cost != d[u]:
            continue
        if u == goal:
            return cost
        for v, w in adj[u]:
            x = cost + w
            if d[v] is None or x < d[v]:
                d[v] = x
                heapq.heappush(heap, (x, v))
    return -1
expected = [shortest(s, t) for s, t in queries]
assert min(expected) == 0 and max(expected) > 1 << 43
assert expected[-3:] == [(1 << 43) - 1, 1 << 43, (1 << 43) + 1]
with tempfile.TemporaryDirectory(prefix='d-cutoff-') as tmp:
    root = Path(tmp)
    (root / 'graph.txt').write_text(f'{n} {len(edges)}\n' + ''.join(f'{u} {v} {w}\n' for u, v, w in edges))
    (root / 'queries.txt').write_text(''.join(f'{s} {t}\n' for s, t in queries))
    for name in sys.argv[1:]:
        subprocess.run([name], env={**os.environ, 'SD_DATA': tmp, 'SD_OUT': tmp}, check=True)
        got = [int(x) for x in (root / 'distances.txt').read_text().splitlines()]
        assert got == expected, (name, got, expected)
print(f'PASS {len(queries)} directed paths including distances above 2^43 and stale/parallel edges')
