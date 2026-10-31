#!/usr/bin/env python3
"""Coarse-key stress for Track D: dense directed graphs whose weights mostly
fall inside one 64-wide bucket (zeros, parallel edges, zero cycles), so nodes
leave a bucket out of distance order and are re-expanded. Every all-pairs
answer is compared with an independent Python Dijkstra.

Usage: same_bucket.py BINARY...
"""
import heapq, os, random, subprocess, sys, tempfile
from pathlib import Path

rng = random.Random(330331)
with tempfile.TemporaryDirectory(prefix='d-coarse33-') as tmp:
    data, out = Path(tmp, 'data'), Path(tmp, 'out')
    data.mkdir(); out.mkdir()
    cases = 0
    for case in range(40):
        n = rng.choice([8, 16, 32, 48])
        density = rng.choice([10, 25, 40])
        edges, adj = [], [[] for _ in range(n)]
        for u in range(n):
            for v in range(n):
                if rng.randrange(100) < density:
                    for _ in range(2 if rng.randrange(6) == 0 else 1):
                        w = rng.choice([0, 0, 0, 1, 2, 31, 63, 64, 65, 127, 128, rng.randrange(200)])
                        edges.append((u, v, w)); adj[u].append((v, w))
        # A long zero-weight chain with shortcuts of weight 63 from node 0.
        if case % 5 == 0:
            for i in range(n - 1):
                edges += [(i, i + 1, 0), (i + 1, i, 0)]
                adj[i].append((i + 1, 0)); adj[i + 1].append((i, 0))
            for i in range(2, n):
                edges.append((0, i, 63)); adj[0].append((i, 63))
        rng.shuffle(edges)
        expected = []
        for s in range(n):
            dist = [None] * n; dist[s] = 0; heap = [(0, s)]
            while heap:
                d, x = heapq.heappop(heap)
                if d != dist[x]:
                    continue
                for y, w in adj[x]:
                    if dist[y] is None or d + w < dist[y]:
                        dist[y] = d + w; heapq.heappush(heap, (d + w, y))
            expected += [f'{-1 if d is None else d}\n' for d in dist]
        (data / 'graph.txt').write_text(f'{n} {len(edges)}\n' + ''.join(f'{u} {v} {w}\n' for u, v, w in edges))
        (data / 'queries.txt').write_text(''.join(f'{s} {t}\n' for s in range(n) for t in range(n)))
        for b in sys.argv[1:]:
            subprocess.run([b], check=True, env=dict(os.environ, SD_DATA=str(data), SD_OUT=str(out)))
            if (out / 'distances.txt').read_text() != ''.join(expected):
                sys.exit(f'FAIL {b} case {case}')
        cases += n * n
print(f'PASS 40 dense same-bucket graphs, {cases} all-pairs queries per binary')
