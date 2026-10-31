#!/usr/bin/env python3
"""Dense directed/parallel/zero-weight graphs with repeated improvements."""
import heapq, os, random, re, subprocess, tempfile
from pathlib import Path
src=(Path(__file__).resolve().parent/'candidate.rs').read_text()
start='let mut best=NONE;let mut dropped=false;let mut exhausted=false;'
assert src.count(start)==1
src=src.replace(start,start+'\n        let mut seen=std::collections::HashSet::<(usize,u32)>::new(); let mut repeats=0u64; let mut inversions=0u64; let mut last_pop=[0u64;2];')
mark='debug_assert_eq!(((d >> BUCKET_SHIFT) as u32) + 1,bucket);'
assert src.count(mark)==1
src=src.replace(mark,mark+'\n                if !seen.insert((side,u)) {repeats+=1;} if d<last_pop[side] {inversions+=1;} last_pop[side]=d;')
mark='self.touched.clear();self.heaps.iter_mut().for_each(FastHeap::clear);'
assert src.count(mark)==1
src=src.replace(mark,mark+'\n        eprintln!("COARSE_COUNTERS {repeats} {inversions}");')
rng=random.Random(821944)
with tempfile.TemporaryDirectory(prefix='d-coarse-adv-') as d:
 p=Path(d); data=p/'data'; out=p/'out';data.mkdir();out.mkdir(); bins=[]
 for cap in (2,16,65536):
  s=p/f'cap{cap}.rs';b=p/f'cap{cap}';s.write_text(src.replace('const POOL_CAP: usize = 65_536;',f'const POOL_CAP: usize = {cap};'))
  subprocess.run(['rustc','--edition=2021','-O','-C','overflow-checks=yes','-C','debug-assertions=yes',str(s),'-o',str(b)],check=True);bins.append((cap,b))
 total_repeats=total_inversions=0
 for case in range(10):
  n=48; edges=[];adj=[[] for _ in range(n)]
  for u in range(n):
   for v in range(n):
    if u!=v and rng.randrange(100)<38:
     for _ in range(2 if rng.randrange(8)==0 else 1):
      w=rng.choice([0,0,1,2,3,31,32,62,63,64,65,127,rng.randrange(128)])
      edges.append((u,v,w));adj[u].append((v,w))
  queries=[(u,v) for u in range(n) for v in range(n)]
  exp=[]
  for u in range(n):
   dist=[10**30]*n;dist[u]=0;h=[(0,u)]
   while h:
    d0,x=heapq.heappop(h)
    if d0!=dist[x]:continue
    for y,w in adj[x]:
     d1=d0+w
     if d1<dist[y]:dist[y]=d1;heapq.heappush(h,(d1,y))
   exp.extend(f'{d if d<10**30 else -1}\n' for d in dist)
  expected=''.join(exp).encode()
  (data/'graph.txt').write_text(f'{n} {len(edges)}\n'+''.join(f'{u} {v} {w}\n' for u,v,w in edges))
  (data/'queries.txt').write_text(''.join(f'{u} {v}\n' for u,v in queries))
  for cap,b in bins:
   result=subprocess.run([str(b)],check=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,env=dict(os.environ,SD_DATA=str(data),SD_OUT=str(out)))
   assert (out/'distances.txt').read_bytes()==expected,(case,cap)
   if cap==65536:
    for a,b0 in re.findall(rb'COARSE_COUNTERS (\d+) (\d+)',result.stderr):total_repeats+=int(a);total_inversions+=int(b0)
 assert total_repeats>0 and total_inversions>0,(total_repeats,total_inversions)
 print(f'PASS 10 dense directed graphs, 23040 pairs at each cap; instrumented repeats={total_repeats}, inversions={total_inversions}')
