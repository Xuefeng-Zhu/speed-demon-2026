#!/usr/bin/env python3
"""Exercise row inline and overflow cutoffs, skewed blocks, and edge weights."""
import heapq, os, random, subprocess, sys, tempfile
from pathlib import Path
binary = Path(sys.argv[1]).resolve()
rng=random.Random(92783)
for n,m in [(1,5000),(2,20001),(17,5000),(128,40000)]:
    edges=[]
    for i in range(m):
        u=0 if i < m*9//10 else rng.randrange(n)
        v=rng.randrange(n)
        w=rng.choice([0,1,2,37,2**32-1,rng.randrange(100000)])
        edges.append((u,v,w))
    edges.extend((0,0,0) for _ in range(5))
    graph=[[] for _ in range(n)]
    for u,v,w in edges: graph[u].append((v,w))
    queries=[(rng.randrange(n),rng.randrange(n)) for _ in range(100)]+[(0,i) for i in range(n)]
    def dist(s,t):
        q=[(0,s)]; d={s:0}
        while q:
            x,u=heapq.heappop(q)
            if x != d[u]: continue
            if u==t: return x
            for v,w in graph[u]:
                z=x+w
                if z < d.get(v,2**64-1): d[v]=z;heapq.heappush(q,(z,v))
        return -1
    expected=''.join(f'{dist(s,t)}\n' for s,t in queries)
    with tempfile.TemporaryDirectory(prefix='sd-d-inline-skew-') as tmp:
        p=Path(tmp); (p/'data').mkdir();(p/'out').mkdir()
        (p/'data'/'graph.txt').write_text(f'{n} {len(edges)}\n'+''.join(f'{u} {v} {w}\n' for u,v,w in edges))
        (p/'data'/'queries.txt').write_text(''.join(f'{s} {t}\n' for s,t in queries))
        subprocess.run([str(binary)],env=dict(os.environ,SD_DATA=str(p/'data'),SD_OUT=str(p/'out')),check=True)
        assert (p/'out'/'distances.txt').read_text()==expected, (n,m)
    print('PASS',n,m,len(queries))
