#!/usr/bin/env python3
"""Exercise graph parser shard cuts and compare distances to independent Dijkstra."""
import heapq, os, random, subprocess, tempfile
from pathlib import Path
rng = random.Random(957218)
binary = '/tmp/d-par-parse-target/release/traverse'
coverage=set()
tests=[]
# The zero-edge graph exercises the body immediately after the header.
tests.append((1, []))
for trial in range(2000):
    n=rng.randrange(1, 10)
    m=rng.randrange(1, 60)
    edges=[(rng.randrange(n),rng.randrange(n),rng.choice([0,1,2,99,65535,4294967295,rng.randrange(2**32)])) for _ in range(m)]
    header=f'{n} {m}\n'.encode()
    body=''.join(f'{u} {v} {w}\n' for u,v,w in edges).encode()
    data=header+body
    found=set()
    for i in range(1,6):
        x=len(header)+len(body)*i//6
        left=data[x-1];right=data[x] if x<len(data) else 10
        kind='newline' if 10 in (left,right) else 'space' if 32 in (left,right) else 'digit'
        found.add((i,kind))
    if found-coverage:
        coverage|=found
        tests.append((n,edges))
    if len(coverage)==15:break
assert len(coverage)==15, sorted(coverage)
with tempfile.TemporaryDirectory(prefix='d-boundary-check-') as tmp:
    root=Path(tmp);data=root/'data';out=root/'out';data.mkdir();out.mkdir()
    for case,(n,edges) in enumerate(tests):
        (data/'graph.txt').write_text(f'{n} {len(edges)}\n'+''.join(f'{u} {v} {w}\n' for u,v,w in edges))
        queries=[(s,t) for s in range(n) for t in range(n)]
        (data/'queries.txt').write_text(''.join(f'{s} {t}\n' for s,t in queries))
        adj=[[] for _ in range(n)]
        for u,v,w in edges: adj[u].append((v,w))
        def shortest(s,t):
            q=[(0,s)]; dist={s:0}
            while q:
                d,u=heapq.heappop(q)
                if d!=dist[u]:continue
                if u==t:return d
                for v,w in adj[u]:
                    nd=d+w
                    if nd<dist.get(v,2**100):dist[v]=nd;heapq.heappush(q,(nd,v))
            return -1
        expected=''.join(f'{shortest(s,t)}\n' for s,t in queries)
        subprocess.run([binary],env={**os.environ,'DATA_DIR':str(data),'OUT_DIR':str(out)},check=True)
        assert (out/'distances.txt').read_text()==expected, f'case {case}'
print(f'PASS {len(tests)} graphs; zero edges and all five shard cuts at digit, space, and newline positions')
