import sys
import random,tempfile,subprocess,os,hashlib
from pathlib import Path
rng=random.Random(923742); n=100; W=2**32-1
edges=[]
for _ in range(500):
 u=rng.randrange(n-5);v=rng.randrange(n-5);w=rng.choice([0,0,1,17,W,W-1,rng.randrange(2**32)]);edges.append((u,v,w))
# Keep node 99 isolated and add parallel/self-loop cases.
edges += [(0,1,W),(0,1,0),(1,1,0),(2,3,W),(3,2,W)]
inf=10**100; dist=[[inf]*n for _ in range(n)]
for i in range(n):dist[i][i]=0
for u,v,w in edges:dist[u][v]=min(dist[u][v],w)
for k in range(n):
 for i in range(n):
  if dist[i][k]==inf: continue
  for j in range(n):
   alt=dist[i][k]+dist[k][j]
   if alt<dist[i][j]:dist[i][j]=alt
q=[]
for i in range(16000):
 if i%9==0: u=v=rng.randrange(n)
 elif i%7==0: u,v=99,rng.randrange(99)
 else: u,v=rng.randrange(99),rng.randrange(99)
 q.append((u,v))
exp=''.join(str(-1 if dist[u][v]>=inf else dist[u][v])+'\n' for u,v in q)
with tempfile.TemporaryDirectory() as tmp:
 root=Path(tmp);data=root/'data';out=root/'out';data.mkdir();out.mkdir();(data/'graph.txt').write_text(f'{n} {len(edges)}\n'+''.join(f'{u} {v} {w}\n' for u,v,w in edges));(data/'queries.txt').write_text(''.join(f'{u} {v}\n' for u,v in q))
 subprocess.run([sys.argv[1]],env=dict(os.environ,SD_DATA=str(data),SD_OUT=str(out)),check=True);actual=(out/'distances.txt').read_text();assert actual==exp
 print('PASS 16000 queries, one worker, repeated epoch wrap; SHA256',hashlib.sha256(actual.encode()).hexdigest())
