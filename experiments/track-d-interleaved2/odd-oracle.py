#!/usr/bin/env python3
"""Independent directed shortest-path and pair-order oracle."""
import heapq
import os
import pathlib
import random
import subprocess
import sys
import tempfile

binary = sys.argv[1]
rng = random.Random(650918)
counts = (0, 1, 3, 5, 7, 17, 31, 200, 201)
with tempfile.TemporaryDirectory() as root:
    path = pathlib.Path(root)
    data, out = path / "data", path / "out"
    data.mkdir()
    out.mkdir()
    cases = 0
    for case in range(32):
        n = rng.randrange(1, 33)
        m = rng.randrange(n * n // 3 + 1)
        edges, adj = [], [[] for _ in range(n)]
        for _ in range(m):
            u, v = rng.randrange(n), rng.randrange(n)
            w = rng.choice((0, 1, 2, 2046, 2047, 2**32 - 1, rng.randrange(2**32)))
            edges.append((u, v, w))
            adj[u].append((v, w))
        (data / "graph.txt").write_text(f"{n} {m}\n" + "".join(f"{u} {v} {w}\n" for u, v, w in edges))

        def shortest(s, t):
            best, heap = {s: 0}, [(0, s)]
            while heap:
                d, u = heapq.heappop(heap)
                if d != best[u]:
                    continue
                if u == t:
                    return d
                for v, w in adj[u]:
                    nd = d + w
                    if nd < best.get(v, 2**100):
                        best[v] = nd
                        heapq.heappush(heap, (nd, v))
            return -1

        for count in counts:
            queries = [(rng.randrange(n), rng.randrange(n)) for _ in range(count)]
            if count >= 3:
                queries[:3] = [(0, 0), (0, n - 1), (0, n - 1)]
            (data / "queries.txt").write_text("".join(f"{s} {t}\n" for s, t in queries))
            expected = "".join(f"{shortest(s, t)}\n" for s, t in queries)
            subprocess.run([binary], check=True, env={**os.environ, "SD_DATA": str(data), "SD_OUT": str(out)}, stdout=subprocess.DEVNULL)
            actual = (out / "distances.txt").read_text()
            assert actual == expected, (case, count)
            cases += 1
print(f"PASS {cases} graphs and ordered query batches including empty and odd lengths")
