import argparse,random,tempfile,pathlib,heapq,os,subprocess
parser=argparse.ArgumentParser(description="Compare executables against independent Dijkstra on randomized graphs")
parser.add_argument("binaries", nargs="+", help="candidate executable paths")
args=parser.parse_args()
rng=random.Random(928347)
with tempfile.TemporaryDirectory() as d:
 p=pathlib.Path(d); data=p/'data'; out=p/'out';data.mkdir();out.mkdir()
 for case in range(80):
  n=rng.randrange(1,65); m=rng.randrange(n*n//3+1); edges=[]; adj=[[] for _ in range(n)]
  for _ in range(m):
   u=rng.randrange(n);v=rng.randrange(n);w=rng.choice([0,0,1,2,99,4294967295,rng.randrange(2**32)])
   edges.append((u,v,w));adj[u].append((v,w))
  q=[(rng.randrange(n),rng.randrange(n)) for _ in range(200)]
  (data/'graph.txt').write_text(f'{n} {m}\n'+''.join(f'{u} {v} {w}\n' for u,v,w in edges))
  (data/'queries.txt').write_text(''.join(f'{u} {v}\n' for u,v in q))
  def shortest(s,t):
   dist={s:0}; hp=[(0,s)]
   while hp:
    x,u=heapq.heappop(hp)
    if x!=dist[u]: continue
    if u==t:return x
    for v,w in adj[u]:
     if x+w<dist.get(v,2**100):dist[v]=x+w;heapq.heappush(hp,(x+w,v))
   return -1
  exp=''.join(f'{shortest(u,v)}\n' for u,v in q)
  for b in args.binaries:
   subprocess.run([b],check=True,env={**os.environ,'DATA_DIR':str(data),'OUT_DIR':str(out),'SD_DATA':str(data),'SD_OUT':str(out)})
   actual=(out/'distances.txt').read_text()
   if actual!=exp: raise SystemExit(f'FAIL {b} case {case}')
 print('PASS 80 random directed graphs; 16000 queries per implementation')
