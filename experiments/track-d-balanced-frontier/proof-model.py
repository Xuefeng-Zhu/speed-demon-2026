import heapq,itertools,random
INF=(1<<64)-1; W=(1<<32)-1

def search(adj,rev,s,t,policy):
 if s==t:return 0
 n=len(adj); ds=[[INF]*n for _ in range(2)]; ds[0][s]=ds[1][t]=0
 hs=[[(0,s)],[(0,t)]]; best=INF; step=0
 while hs[0] and hs[1]:
  a,b=hs[0][0][0],hs[1][0][0]
  if a+b>=best:break
  if policy=='shorter':side=int(len(hs[0])>len(hs[1]))
  elif policy=='longer':side=int(len(hs[0])<len(hs[1]))
  elif policy=='alternate':side=step&1
  elif policy=='forward':side=0
  else:side=int(a>b)
  step+=1; d,u=heapq.heappop(hs[side])
  if d>ds[side][u]:continue
  for v,w in (adj if side==0 else rev)[u]:
   nd=d+w
   if nd<ds[side][v]:
    ds[side][v]=nd; heapq.heappush(hs[side],(nd,v))
    if ds[1-side][v]!=INF:best=min(best,nd+ds[1-side][v])
 return best

def verify(n,edges):
 adj=[[] for _ in range(n)];rev=[[] for _ in range(n)]; fw=[[INF]*n for _ in range(n)]
 for i in range(n):fw[i][i]=0
 for u,v,w in edges:adj[u].append((v,w));rev[v].append((u,w));fw[u][v]=min(fw[u][v],w)
 for k in range(n):
  for i in range(n):
   for j in range(n):fw[i][j]=min(fw[i][j],fw[i][k]+fw[k][j])
 for s in range(n):
  for t in range(n):
   for p in ('shorter','longer','alternate','forward','min_distance'):
    got=search(adj,rev,s,t,p)
    if got!=fw[s][t]:raise AssertionError((n,edges,s,t,p,got,fw[s][t]))
# Each directed non-loop edge absent, zero, one, or max weight.
pairs=[(i,j) for i in range(3) for j in range(3) if i!=j]
for code in itertools.product((None,0,1,W),repeat=len(pairs)):
 verify(3,[(u,v,w) for (u,v),w in zip(pairs,code) if w is not None])
rng=random.Random(481516)
for case in range(1000):
 n=rng.randint(1,10); edges=[(rng.randrange(n),rng.randrange(n),rng.choice((0,1,2,20,W,rng.randrange(10000)))) for _ in range(rng.randrange(2*n*n+1))]
 verify(n,edges)
print('PASS 4096 exhaustive 3-node directed graphs and 1000 randomized directed multigraphs; five side-selection policies; all-pairs Floyd-Warshall oracle')
