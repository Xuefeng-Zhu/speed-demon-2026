#!/usr/bin/env python3
import itertools,os,random,subprocess,sys,tempfile
from pathlib import Path
repo=Path(__file__).resolve().parents[2]
s=(repo/'experiments/b-global-queries/shared.rs').read_text(); ref=repo/'official/reference/b_index.py'
a='let nthreads = thread::available_parallelism().map_or(4, |n| n.get());';b='let cache = DenseCache::new(plan.keys.len(), 64 * 1024 * 1024);';assert s.count(a)==s.count(b)==1
terms=['a','b','c','d','z','never'];queries=[]
for length in range(1,7):
 for ops in itertools.product(('AND','OR','NOT'),repeat=length-1):
  for shift in range(6):
   ts=[terms[(shift+i)%6] for i in range(length)]
   queries.append('BOOL '+ts[0]+''.join(' '+op+' '+t for op,t in zip(ops,ts[1:])))
rng=random.Random(128843)
for _ in range(1800):
 n=rng.randint(1,6);ts=[rng.choice(terms) for _ in range(n)];queries.append('BOOL '+ts[0]+''.join(' '+rng.choice(('AND','OR','NOT'))+' '+t for t in ts[1:]))
queries.extend(['PHRASE "a b"','PHRASE "a a"','PHRASE "never a"','PHRASE "a b"','BOOL a AND never OR c','BOOL a OR b AND never NOT c','BOOL never OR a AND z']*8)
with tempfile.TemporaryDirectory(prefix='b-global-review-') as td:
 root=Path(td);specs=[(1,None),(2,None),(3,None),(7,None),(12,None),(32,None),(7,0),(7,8)];bins=[]
 for j,(workers,cap) in enumerate(specs):
  text=s.replace(a,f'let nthreads = {workers};')
  if cap is not None:text=text.replace(b,f'let cache = DenseCache::new(plan.keys.len(), {cap});')
  src=root/f's{j}.rs';exe=root/f'e{j}';src.write_text(text)
  subprocess.run(['rustc','--edition=2021','-O','-C','overflow-checks=yes',str(src),'-o',str(exe)],check=True,stderr=subprocess.DEVNULL);bins.append(exe)
 total=0
 for n in [0,1,2,7,63,64,65,127,128,129]:
  data=root/f'data{n}';out=root/f'out{n}';expected=root/f'ref{n}'
  for d in (data,out,expected):d.mkdir()
  rows=[]
  for i in range(n):
   mask=(i*13+i//7)%16;words=[terms[k] for k in range(4) if mask>>k&1]
   if i%5==0:words+=['a','a']
   rows.append(f'{i}\t'+' — '.join(words)+'\n')
  (data/'docs.txt').write_text(''.join(rows));(data/'queries.txt').write_text('\n'.join(queries)+'\n')
  subprocess.run([sys.executable,str(ref),'--data',str(data),'--out',str(expected)],check=True,stdout=subprocess.DEVNULL)
  want=(expected/'results.txt').read_bytes()
  for (workers,cap),exe in zip(specs,bins):
   subprocess.run([str(exe)],env={**os.environ,'SD_DATA':str(data),'SD_OUT':str(out)},check=True,stdout=subprocess.DEVNULL)
   got=(out/'results.txt').read_bytes();assert got==want,(n,workers,cap)
   total+=len(queries)
  print('PASS docs',n,'eight worker/cache settings',flush=True)
 print('PASS',total,'query comparisons against official reference')
