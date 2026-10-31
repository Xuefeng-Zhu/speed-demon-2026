#!/usr/bin/env python3
"""Directed paths/cycles, one-way cuts, duplicate edges, query pins and wide weights."""
import heapq,os,random,subprocess,sys,tempfile
from pathlib import Path
b=Path(sys.argv[1]).resolve(); rng=random.Random(84053)
with tempfile.TemporaryDirectory(prefix='d-chain-stress-') as tmp:
 p=Path(tmp);d=p/'data';o=p/'out';d.mkdir();o.mkdir()
 for n in list(range(2,45))+[48,65,80,120]:
  for variant in range(8):
   edges=[]
   for i in range(n-1):
    wa = [0,1,2**32-1, 2**31, rng.randrange(1,200)][(i+variant)%5]
    wb = [1,0,2**32-1, 3, rng.randrange(1,200)][(i*3+variant)%5]
    if (variant+i)%7 != 0: edges.append((i,i+1,wa))
    if (variant+2*i)%9 != 0: edges.append((i+1,i,wb))
    if i%4==0: edges.extend([(i,i+1,wa),(i,i+1,min(wa+1,2**32-1))])
    if i%5==0: edges.extend([(i,i,0),(i,i,2**32-1)])
   if variant%2: edges.extend([(n-1,0,0),(0,n-1,4)])
   if not edges: edges=[(0,0,0)]
   # At most one intermediate query pin per instance: other interiors remain eligible.
   qs=[(0,n-1),(n-1,0)]
   if variant%3==0: qs.append((n//2,n-1))
   g=[[] for _ in range(n)]
   for u,v,w in edges:g[u].append((v,w))
   def sp(s,t):
    hp=[(0,s)];best={s:0}
    while hp:
     x,u=heapq.heappop(hp)
     if x!=best[u]:continue
     if u==t:return x
     for v,w in g[u]:
      a=x+w
      if a<best.get(v,2**100):best[v]=a;heapq.heappush(hp,(a,v))
    return -1
   (d/'graph.txt').write_text(f'{n} {len(edges)}\n'+''.join(f'{u} {v} {w}\n' for u,v,w in edges));(d/'queries.txt').write_text(''.join(f'{u} {v}\n' for u,v in qs))
   subprocess.run([str(b)],check=True,stdout=subprocess.DEVNULL,env=dict(os.environ,SD_DATA=str(d),SD_OUT=str(o)))
   got=(o/'distances.txt').read_text();expected=''.join(f'{sp(u,v)}\n' for u,v in qs)
   if got!=expected: raise SystemExit(f'FAIL n={n} variant={variant}: {got!r} != {expected!r}')
 print('PASS', (43+4)*8,'directed chain/cycle cases')
