import heapq,itertools,random
INF=(1<<64)-1; W=(1<<32)-1

def search(adj,rev,s,t):
 if s==t:return 0
 n=len(adj);ds=[[INF]*n for _ in range(2)];ds[0][s]=ds[1][t]=0
 hs=[[(0,s)],[(0,t)]];last=[0,0];best=INF
 while hs[0] and hs[1]:
  assert last[0]<=hs[0][0][0] and last[1]<=hs[1][0][0]
  if len(hs[0])<len(hs[1]):side=0
  elif len(hs[0])>len(hs[1]):side=1
  else:side=int(last[0]>last[1])
  d=hs[side][0][0];last[side]=d;other=1-side
  if min(INF,d+last[other])>=best:
   last[other]=hs[other][0][0]
   if min(INF,d+last[other])>=best:break
  d,u=heapq.heappop(hs[side])
  if d>ds[side][u]:continue
  for v,w in (adj if side==0 else rev)[u]:
   nd=d+w
   if nd<ds[side][v]:
    assert nd>=last[side]
    ds[side][v]=nd;heapq.heappush(hs[side],(nd,v))
    if ds[other][v]!=INF:best=min(best,nd+ds[other][v])
 return best

def verify(n,edges):
 adj=[[] for _ in range(n)];rev=[[] for _ in range(n)];fw=[[INF]*n for _ in range(n)]
 for i in range(n):fw[i][i]=0
 for u,v,w in edges:adj[u].append((v,w));rev[v].append((u,w));fw[u][v]=min(fw[u][v],w)
 for k in range(n):
  for i in range(n):
   for j in range(n):fw[i][j]=min(fw[i][j],fw[i][k]+fw[k][j])
 for s in range(n):
  for t in range(n):
   got=search(adj,rev,s,t)
   if got!=fw[s][t]:raise AssertionError((n,edges,s,t,got,fw[s][t]))
pairs=[(i,j) for i in range(3) for j in range(3) if i!=j]
for code in itertools.product((None,0,1,W),repeat=len(pairs)):
 verify(3,[(u,v,w) for (u,v),w in zip(pairs,code) if w is not None])
rng=random.Random(888999)
for case in range(1000):
 n=rng.randint(1,10);edges=[(rng.randrange(n),rng.randrange(n),rng.choice((0,1,2,20,W,rng.randrange(10000)))) for _ in range(rng.randrange(2*n*n+1))];verify(n,edges)
print('PASS 4096 exhaustive 3-node directed graphs and 1000 random directed multigraphs; lazy-top policy; all-pairs Floyd-Warshall oracle')
