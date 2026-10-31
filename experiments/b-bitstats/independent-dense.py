#!/usr/bin/env python3
import hashlib,os,random,subprocess,sys,tempfile
from pathlib import Path
source=Path(sys.argv[1] if len(sys.argv)>1 else Path(__file__).resolve().parent/'candidate.rs').resolve()
reference=Path(sys.argv[2] if len(sys.argv)>2 else Path(__file__).resolve().parents[2]/'official/reference/b_index.py').resolve()
body=source.read_text(); needle='let nthreads = thread::available_parallelism().map_or(4, |n| n.get());'; assert body.count(needle)==1
counts=[0,1,7,8,9,63,64,65,127,128,129,2047,2048,2049,4095,4096,4097,8191,8192,8193]
workers=[1,2,7,32]; cases=0
with tempfile.TemporaryDirectory(prefix='bitstats-dense-') as td:
 root=Path(td); bins={}
 for n in workers:
  src=root/f'w{n}.rs';src.write_text(body.replace(needle,f'let nthreads = {n};'));bins[n]=root/f'w{n}'
  subprocess.run(['rustc','--edition=2021','-O','-C','overflow-checks=yes',str(src),'-o',str(bins[n])],check=True)
 for n in counts:
  dat=root/f'data{n}';ref=root/f'ref{n}';dat.mkdir();ref.mkdir();rng=random.Random(7070+n)
  with (dat/'docs.txt').open('w') as f:
   for d in range(n):
    a=['all','alpha']
    if d%2==0:a+=['even']
    if d%3==0:a+=['third']
    if d%8<7:a+=['seven']
    if d%16<8:a+=['eight']
    if d%16<9:a+=['nine']
    if d%64==63:a+=['last']
    if d%101==0:a+=['sparse']
    f.write(f'{d}\t'+(' '.join(a) if d%53 else '')+'\n')
  terms=['all','alpha','even','third','seven','eight','nine','last','sparse','absent']; queries=['BOOL '+t for t in terms]
  queries += ['BOOL all NOT even','BOOL all OR even AND third','BOOL all AND even NOT seven','BOOL all OR sparse NOT all','PHRASE "all alpha"']
  for _ in range(150):
   size=rng.randrange(1,7); seq=[rng.choice(terms) for _ in range(size)]
   queries.append('BOOL '+seq[0]+''.join(' '+rng.choice(['AND','OR','NOT'])+' '+x for x in seq[1:]))
  (dat/'queries.txt').write_text('\n'.join(queries)+'\n')
  subprocess.run([sys.executable,str(reference),'--data',str(dat),'--out',str(ref)],check=True,stdout=subprocess.DEVNULL)
  expected=(ref/'results.txt').read_bytes()
  for w in workers:
   out=root/f'out{n}-{w}';out.mkdir();env=dict(os.environ,SD_DATA=str(dat),SD_OUT=str(out));subprocess.run([str(bins[w])],env=env,check=True)
   actual=(out/'results.txt').read_bytes()
   if actual!=expected: raise SystemExit(f'mismatch docs={n} workers={w}')
   cases+=1
print('PASS',cases,'dense/reference comparisons; queries per case',len(queries),flush=True)
