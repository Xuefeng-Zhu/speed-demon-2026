#!/usr/bin/env python3
"""Runtime Dijkstra oracle on sparse/dense graphs, pinned endpoints and cap fallback."""
import heapq, os, pathlib, random, subprocess, sys, tempfile
rng=random.Random(6879021)
binary=pathlib.Path(sys.argv[1]).resolve(); forced=pathlib.Path(sys.argv[2]).resolve()
U=2**32-1
with tempfile.TemporaryDirectory() as td:
 root=pathlib.Path(td); data=root/'data';out=root/'out';data.mkdir();out.mkdir()
 successes=cases=0
 def run(n,edges,queries,second_fallback=False,expected_trace=None):
  global successes,cases
  cases+=1
  (data/'graph.txt').write_text(f'{n} {len(edges)}\n'+''.join(f'{u} {v} {w}\n' for u,v,w in edges))
  (data/'queries.txt').write_text(''.join(f'{u} {v}\n' for u,v in queries))
  adj=[[] for _ in range(n)]
  for u,v,w in edges:adj[u].append((v,w))
  def solve(s,t):
   dist={s:0};h=[(0,s)]
   while h:
    d,u=heapq.heappop(h)
    if d!=dist[u]:continue
    if u==t:return d
    for v,w in adj[u]:
     nd=d+w
     if nd<dist.get(v,1<<100):dist[v]=nd;heapq.heappush(h,(nd,v))
   return -1
  expected=''.join(f'{solve(s,t)}\n' for s,t in queries)
  for target in (binary,forced):
   p=subprocess.run([str(target)],env={**os.environ,'SD_DATA':str(data),'SD_OUT':str(out),'SD_CONTRACT_TRACE':'1'},capture_output=True,text=True,check=True)
   if (out/'distances.txt').read_text()!=expected:raise AssertionError((cases,target,p.stderr))
   lines=p.stderr.splitlines()
   if len(lines)!=2:raise AssertionError((cases,target,lines))
   if target==binary and second_fallback and not lines[1].startswith('contract fallback '):raise AssertionError((cases,'second round did not fall back',lines))
   if target==binary and expected_trace is not None and lines!=expected_trace:raise AssertionError((cases,'unexpected trace',lines))
   successes+=sum(x.startswith('contract bound ') for x in lines)
   if target==forced and edges and 'contract fallback' not in p.stderr:raise AssertionError((cases,'no forced fallback',lines))
 # Each graph has few pinned endpoints so most intermediate vertices remain eligible.
 for i in range(120):
  n=rng.randrange(12,85);pool=[0,n-1,n//2];q=[(rng.choice(pool),rng.choice(pool)) for _ in range(10)]
  edges=[]
  if i%3==0:
   for u in range(n-1):
    for a,b in ((u,u+1),(u+1,u)):
     if rng.random()<0.9:edges.append((a,b,rng.choice([0,1,2,23,U-1,U])))
   for j in range(n//5):
    u=rng.randrange(n);v=rng.randrange(n);edges.append((u,v,rng.choice([0,1,U])))
  elif i%3==1:
   for _ in range(3*n):
    u=rng.randrange(n);v=rng.randrange(n);edges.append((u,v,rng.choice([0,1,7,42,U])))
  else:
   # Dense rows trigger exclusion by degree; loops and parallel arcs are legal.
   for u in range(n):
    for v in range(n):
     if rng.random()<0.25:edges.append((u,v,rng.choice([0,1,71,U])))
  run(n,edges,q)
 # Disjoint 3-in/3-out stars can grow from six edges to nine per removed node.
 # Connector IDs exceed centers, making every center eligible and independent.
 for k in (1,2,16,80):
  n=7*k; edges=[]
  for c in range(k):
   for j in range(3):edges.append((k+6*c+j,c,j))
   for j in range(3):edges.append((c,k+6*c+3+j,j+1))
  q=[(k,k+3),(k+2,k+5),(k+1,k+5),(k+3,k),(k+3,k+3)]
  run(n,edges,q)
 # Exhaustive three-node directed graphs; one node in every component stays
 # unpinned so the production transformation is exercised. Components are
 # disjoint, and Python Dijkstra computes all requested answers independently.
 choices=(None,0,1,U); pairs=((0,1),(0,2),(1,0),(1,2),(2,0),(2,1)); edges=[];q=[]
 for code in range(4**6):
  digits=code
  for a,b in pairs:
   w=choices[digits%4];digits//=4
   if w is not None:edges.append((3*code+a,3*code+b,w))
  q.extend(((3*code,3*code+1),(3*code+1,3*code)))
 run(3*4**6,edges,q)
 # Directed chain exercises two successful reductions, with both endpoints pinned.
 run(10,[(u,u+1,1) for u in range(9)],[(0,9),(9,0)],expected_trace=['contract bound 8 18','contract bound 7 18'])
 # Two center nodes form opposite 3x3 bipartite shortcuts after round one.
 # Round two has a conservative 27-edge bound above the 24-edge cap and
 # must retain the first-round graph without allocating the second graph.
 edges=[(u,0,1) for u in (2,3,4)]+[(0,v,1) for v in (5,6,7)]
 edges += [(u,1,1) for u in (5,6,7)]+[(1,v,1) for v in (2,3,4)]
 run(8,edges,[(5,5)],second_fallback=True)
 print(f'PASS {cases} sparse/dense/maximum-weight/pinned/star graphs, {cases*2} binary comparisons, {successes} ordinary contraction rounds and natural second-round cap fallback')
