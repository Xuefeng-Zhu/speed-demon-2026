import heapq, os, random, subprocess, tempfile
from pathlib import Path
rng=random.Random(151789)
with tempfile.TemporaryDirectory(prefix='d-parse-partitions-') as td:
 root=Path(td);data=root/'data';out=root/'out';data.mkdir();out.mkdir();total=0
 source=(Path(__file__).resolve().parent/'combined.rs').read_text()
 original='let threads = thread::available_parallelism().map_or(1, |n| n.get());'
 assert source.count(original)==1
 for t in (1,2,3,6,9,12,32):
  path=root/f't{t}.rs'; path.write_text(source.replace(original, f'let threads = {t}usize;'))
  subprocess.run(['rustc','--edition=2021','-O',str(path),'-o',str(root/f't{t}')],check=True)
 for threads in (1,2,3,6,9,12,32):
  required={(i,k) for i in range(1,threads) for k in ('digit','space','newline')}; coverage=set(); graphs=[(1,[])]
  for _ in range(6000):
   n=rng.randrange(1,16);m=rng.randrange(1,140); e=[(rng.randrange(n),rng.randrange(n),rng.choice([0,1,9,10,99,4294967295,rng.randrange(2**32)])) for _ in range(m)]
   raw=(f'{n} {m}\n'+''.join(f'{u} {v} {w}\n' for u,v,w in e)).encode(); found=set()
   for i in range(1,threads):
    x=1+i*(len(raw)-1)//threads
    b=raw[x-1]; found.add((i,'newline' if b==10 else 'space' if b==32 else 'digit'))
   if found-coverage: graphs.append((n,e));coverage|=found
   if required<=coverage:break
  assert required<=coverage,(threads,required-coverage)
  for n,e in graphs:
   (data/'graph.txt').write_text(f'{n} {len(e)}\n'+''.join(f'{u} {v} {w}\n' for u,v,w in e));q=[(u,v) for u in range(n) for v in range(n)];(data/'queries.txt').write_text(''.join(f'{u} {v}\n' for u,v in q));adj=[[] for _ in range(n)]
   for u,v,w in e:adj[u].append((v,w))
   def distance(s,t):
    ds={s:0};h=[(0,s)]
    while h:
     d,u=heapq.heappop(h)
     if d!=ds[u]:continue
     if u==t:return d
     for v,w in adj[u]:
      x=d+w
      if x<ds.get(v,2**100):ds[v]=x;heapq.heappush(h,(x,v))
    return -1
   expected=''.join(f'{distance(u,v)}\n' for u,v in q);p=out/'distances.txt';p.unlink(missing_ok=True)
   subprocess.run([str(root/f't{threads}')],env={**os.environ,'SD_DATA':str(data),'SD_OUT':str(out)},check=True)
   assert p.read_text()==expected,(threads,n,e);total+=1
  print('PASS',threads,'workers',len(graphs),'graphs',len(required),'shard-cut categories',flush=True)
 print('PASS total graphs',total)
