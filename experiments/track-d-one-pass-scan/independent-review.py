import os, pathlib, random, subprocess, tempfile
ROOT=pathlib.Path(__file__).resolve().parent
source=pathlib.Path(os.environ.get('D_REVIEW_SOURCE',str(ROOT/'combined.rs'))).read_text()
needle='let threads = thread::available_parallelism().map_or(1, |n| n.get());'
assert source.count(needle)==1
workers=(1,2,3,7,12,32)
with tempfile.TemporaryDirectory(prefix='d-parse-review-') as td:
 root=pathlib.Path(td)
 for t in workers:
  p=root/f's{t}.rs';p.write_text(source.replace(needle,f'let threads = {t};'))
  subprocess.run(['rustc','--edition','2021','-O',str(p),'-o',str(root/f'b{t}')],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
 count=0
 for seed in range(110):
  rng=random.Random(seed); n=rng.randint(1,20); m=seed if seed<40 else rng.randint(0,90)
  edges=[(rng.randrange(n),rng.randrange(n),rng.choice((0,1,9,10,99,100,4294967294,4294967295))) for _ in range(m)]
  graph=f'{n} {m}\n'+''.join(f'{u} {v} {w}\n' for u,v,w in edges)
  inf=10**30; dist=[[inf]*n for _ in range(n)]
  for i in range(n):dist[i][i]=0
  for u,v,w in edges:dist[u][v]=min(dist[u][v],w)
  for k in range(n):
   for i in range(n):
    for j in range(n):dist[i][j]=min(dist[i][j],dist[i][k]+dist[k][j])
  pairs=[(i,j) for i in range(n) for j in range(n)]
  expect=''.join(f'{dist[i][j] if dist[i][j]<inf else -1}\n' for i,j in pairs)
  d=root/'data';o=root/'out';d.mkdir(exist_ok=True);o.mkdir(exist_ok=True)
  (d/'graph.txt').write_text(graph);(d/'queries.txt').write_text(''.join(f'{i} {j}\n' for i,j in pairs))
  for t in workers:
   out=o/'distances.txt';out.unlink(missing_ok=True)
   subprocess.run([str(root/f'b{t}')],env=dict(os.environ,SD_DATA=str(d),SD_OUT=str(o)),check=True,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
   if out.read_text()!=expect:raise RuntimeError(f'fail seed {seed}, threads {t}')
   count+=len(pairs)
 print('PASS',110,'graphs,',len(workers),'worker counts,',count,'oracle answers')
