#!/usr/bin/env python3
"""Exercise exact batch4 with adversarial weights against independent Dijkstra.

This temporary instrumentation only counts visits after the first pop in a
batch. It does not modify the production source or keep generated data.
"""
import hashlib
import heapq
import os
from pathlib import Path
import random
import re
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / 'experiments/track-d-hybrid-samekey15/batch4.rs'
rng = random.Random(0x905ac09)

def oracle(n, edges, s, t):
    adj = [[] for _ in range(n)]
    for u, v, w in edges:
        adj[u].append((v, w))
    dist = [None] * n
    dist[s] = 0
    todo = [(0, s)]
    while todo:
        d, u = heapq.heappop(todo)
        if dist[u] != d:
            continue
        if u == t:
            return d
        for v, w in adj[u]:
            x = d + w
            if dist[v] is None or x < dist[v]:
                dist[v] = x
                heapq.heappush(todo, (x, v))
    return -1

def fixture(n, edges, queries):
    return (n, edges, queries)

cases = []
for size in (1, 2, 7, 8, 9, 15, 16, 17, 31, 32, 33, 63):
    edges = [(0, i, 0) for i in range(1, size)]
    edges += [(i, 0, 0) for i in range(1, size)]
    edges += [(i, (i + 1) % size, 0) for i in range(size)]
    edges += [(0, i, 1000) for i in range(1, size)]
    queries = [(i, j) for i in range(size) for j in range(size)]
    cases.append(fixture(size, edges, queries))
for _ in range(100):
    n = rng.randrange(1, 65)
    edges = []
    for _ in range(rng.randrange(n * 7 + 1)):
        w = rng.choice([0, 0, 0, 1, 1, 2, 3, 0xFFFFFFFF, rng.randrange(2**32)])
        edges.append((rng.randrange(n), rng.randrange(n), w))
    queries = [(rng.randrange(n), rng.randrange(n)) for _ in range(100)]
    cases.append(fixture(n, edges, queries))

with tempfile.TemporaryDirectory(prefix='d-samekey-review-') as td:
    p = Path(td)
    data, out = p / 'data', p / 'out'
    data.mkdir(); out.mkdir()
    source = SRC.read_text()
    begin = 'use std::fs::{self, File};'
    assert source.count(begin) == 1
    source = source.replace(begin, 'static EXTRA_BATCH_POPS: std::sync::atomic::AtomicUsize = std::sync::atomic::AtomicUsize::new(0);\n' + begin)
    start = 'for _ in 0..4 {\n                if self.heaps[side].head[0]==END {break;}'
    replacement = ('for batch_index in 0..4 {\n'
                   '                if self.heaps[side].head[0]==END {break;}\n'
                   '                if batch_index > 0 { EXTRA_BATCH_POPS.fetch_add(1, std::sync::atomic::Ordering::Relaxed); }')
    assert source.count(start) == 1
    source = source.replace(start, replacement)
    end = 'fs::write(format!("{out}/distances.txt"), text).unwrap();'
    assert source.count(end) == 1
    source = source.replace(end, end + '\n    eprintln!("EXTRA_BATCH_POPS={}", EXTRA_BATCH_POPS.load(std::sync::atomic::Ordering::Relaxed));')
    local = p / 'instrumented.rs'
    local.write_text(source)
    binary = p / 'batch4'
    subprocess.run(['rustc', '--edition=2021', '-O', '-C', 'overflow-checks=yes', '-C', 'debug-assertions=yes', str(local), '-o', str(binary)], check=True)
    total_answers = total_extra = 0
    for case, (n, edges, queries) in enumerate(cases):
        (data / 'graph.txt').write_text(f'{n} {len(edges)}\n' + ''.join(f'{u} {v} {w}\n' for u, v, w in edges))
        (data / 'queries.txt').write_text(''.join(f'{u} {v}\n' for u, v in queries))
        expected = [str(oracle(n, edges, s, t)) for s, t in queries]
        result = subprocess.run([str(binary)], env={**os.environ, 'SD_DATA':str(data), 'SD_OUT':str(out)}, capture_output=True, text=True, check=True)
        match = re.search(r'EXTRA_BATCH_POPS=(\d+)', result.stderr)
        assert match, (case, result.stderr)
        total_extra += int(match.group(1))
        actual = (out / 'distances.txt').read_text().splitlines()
        assert actual == expected, (case, expected[:10], actual[:10])
        total_answers += len(expected)
    assert total_extra > 0
    print(f'PASS {len(cases)} graphs, {total_answers} queries, {total_extra} additional same-batch pops; source SHA-256 {hashlib.sha256(SRC.read_bytes()).hexdigest()}')
