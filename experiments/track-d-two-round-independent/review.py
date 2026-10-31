#!/usr/bin/env python3
"""Independent Floyd and CSR transpose validation of production contract()."""
import collections, hashlib, os, pathlib, random, subprocess, tempfile
root=pathlib.Path(__file__).resolve().parents[1]; src=(root/'track-d-two-round/meeting.rs').read_text()
assert hashlib.sha256(src.encode()).hexdigest()=='6673a36206ac04e4154337a5ef90b774d3b35eb3b375d7bbe8430244d55eb709'
assert src.count('fn main() {')==1
src=src.replace('fn main() {','fn unused_main() {')
src+='''
fn dump(g:&[Csr;2], path:&str) {
 let mut t=String::new();
 for side in 0..2 {for u in 0..g[side].first.len()-1 {for(v,w) in g[side].edges(u as u32){t.push_str(&format!("{} {} {} {}\\n",side,u,v,w));}}}
 fs::write(path,t).unwrap();
}
fn main() {
 let data=std::env::var("SD_DATA").unwrap(); let out=std::env::var("SD_OUT").unwrap();
 let g=load_graph(&format!("{data}/graph.txt"),4);
 let input=fs::read(format!("{data}/queries.txt")).unwrap(); let mut it=numbers(&input);let mut q=Vec::new();
 while let(Some(s),Some(t))=(it.next(),it.next()){q.push((s,t));}
 let cap=g[0].adj.len().saturating_mul(2).min(5_000_000);
 let g=contract(g,&q,4,cap);dump(&g,&format!("{out}/one"));
 let g=contract(g,&q,4,cap);dump(&g,&format!("{out}/two"));
}
'''
R=random.Random(1239874); W=2**32-1
with tempfile.TemporaryDirectory() as d:
 p=pathlib.Path(d); (p/'data').mkdir();(p/'out').mkdir(); (p/'review.rs').write_text(src)
 subprocess.run(['rustc','--edition=2021','-C','opt-level=1','-C','overflow-checks=yes','-C','debug-assertions=yes',str(p/'review.rs'),'-o',str(p/'review')],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
 for case in range(120):
  n=R.randrange(4,26); edges=[]
  # Half low-degree directed skeletons encourage active contractions;
  # others include dense components, parallel arcs, loops, and extreme weights.
  if case%2:
   for u in range(n-1):
    for v in (u,u+1):
     if R.random()<0.85:edges.append((u,v,R.choice([0,1,5,W])))
    if R.random()<0.8:edges.append((u+1,u,R.choice([0,1,5,W])))
  else:
   for i in range(R.randrange(n,5*n)):
    u,v=R.randrange(n),R.randrange(n); edges.append((u,v,R.choice([0,0,1,5,W-1,W])))
    if R.random()<0.1:edges.append(edges[-1])
  s,t=R.sample(range(n),2); queries=[(s,t),(t,s),(s,s)]
  (p/'data/graph.txt').write_text(f'{n} {len(edges)}\n'+''.join(f'{a} {b} {w}\n' for a,b,w in edges))
  (p/'data/queries.txt').write_text(''.join(f'{a} {b}\n' for a,b in queries))
  subprocess.run([str(p/'review')],env={**os.environ,'SD_DATA':str(p/'data'),'SD_OUT':str(p/'out')},check=True,stdout=subprocess.DEVNULL)
  def floyd(arcs):
   inf=10**30; D=[[0 if x==y else inf for y in range(n)]for x in range(n)]
   for a,b,w in arcs:D[a][b]=min(D[a][b],w)
   for k in range(n):
    for a in range(n):
     for b in range(n):D[a][b]=min(D[a][b],D[a][k]+D[k][b])
   return [D[a][b] for a,b in queries]
  expected=floyd(edges)
  for f in ('one','two'):
   byside=[[],[]]
   for line in (p/'out'/f).read_text().splitlines():
    side,a,b,w=map(int,line.split());assert 0<=w<=W;byside[side].append((a,b,w))
   assert collections.Counter((b,a,w) for a,b,w in byside[0])==collections.Counter(byside[1]),(case,f,'transpose')
   assert floyd(byside[0])==expected,(case,f,'distances')
   assert len(byside[0])<=min(2*len(edges),5_000_000),(case,f,'cap')
 print('PASS 120 graphs, 240 transformed CSRs: Floyd distances, forward/reverse multiset equivalence, per-round edge caps')
