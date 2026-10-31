#!/usr/bin/env python3
"""Exercise actual selected-derived corridor implementation against exact Dijkstra."""
from pathlib import Path
import hashlib,heapq,os,random,subprocess,tempfile
here=Path(__file__).resolve().parent
root=here.parents[1]
src=(here/'candidate.rs').read_text()
marker='const POOL_CAP: usize = 65_536;'; assert src.count(marker)==1
rng=random.Random(918273)
with tempfile.TemporaryDirectory(prefix='d-corridor19-') as td:
 p=Path(td);bins=[]
 for cap in (0,1,2,16,65536):
  for threads in (1,7):
   target=p/f'c{cap}-t{threads}';text=src.replace(marker,f'const POOL_CAP: usize = {cap};')
   match='let threads = thread::available_parallelism().map_or(1, |n| n.get()).min(12);';assert text.count(match)==1
   text=text.replace(match,f'let threads = {threads};'); source=target.with_suffix('.rs');source.write_text(text)
   subprocess.run(['rustc','--edition=2021','-O','-C','overflow-checks=yes','-C','debug-assertions=yes',str(source),'-o',str(target)],check=True);bins.append(str(target))
 for script in ('oracle.py','exhaustive.py'):
  subprocess.run(['python3',str(root/'experiments/track-d-balanced-frontier'/script),*bins],check=True)
 subprocess.run(['python3',str(root/'experiments/track-d-u32-fallback/thresholds.py'),*bins],check=True)
 # Road-like and adversarial directed multi-graphs with long chains and cycles.
 for case in range(36):
  n=2+rng.randrange(158);adj=[[] for _ in range(n)]; edges=[]
  def edge(u,v,w):edges.append((u,v,w));adj[u].append((v,w))
  W=[0,0,1,2,200,2047,2**32-1,2**32-2]
  for u in range(n-1):
   if rng.random()<.93:edge(u,u+1,rng.choice(W))
   if rng.random()<.93:edge(u+1,u,rng.choice(W))
  for _ in range(n//5):
   u=rng.randrange(n);v=rng.choice([u,max(0,u-1),min(n-1,u+1),rng.randrange(n)]);edge(u,v,rng.choice(W))
  if case%3==0:edge(n-1,0,0);edge(0,n-1,0)
  qs=[(rng.randrange(n),rng.randrange(n)) for _ in range(200)]+[(0,n-1),(n-1,0),(0,0)]
  def dist(s,t):
   ds=[2**100]*n;ds[s]=0;h=[(0,s)]
   while h:
    d,u=heapq.heappop(h)
    if d!=ds[u]:continue
    if u==t:return d
    for v,w in adj[u]:
     nd=d+w
     if nd<ds[v]:ds[v]=nd;heapq.heappush(h,(nd,v))
   return -1
  expected=''.join(f'{dist(s,t)}\n' for s,t in qs)
  data=p/'data';out=p/'out';data.mkdir(exist_ok=True);out.mkdir(exist_ok=True)
  (data/'graph.txt').write_text(f'{n} {len(edges)}\n'+''.join(f'{u} {v} {w}\n' for u,v,w in edges));(data/'queries.txt').write_text(''.join(f'{s} {t}\n' for s,t in qs))
  for b in bins:
   subprocess.run([b],check=True,env=dict(os.environ,SD_DATA=str(data),SD_OUT=str(out)))
   if (out/'distances.txt').read_text()!=expected:raise RuntimeError(f'case={case}, binary={b}')
 print('PASS 36 road-like directed multigraphs / 7,308 answers each, ten cap/worker builds')
print('candidate SHA-256',hashlib.sha256(src.encode()).hexdigest())
