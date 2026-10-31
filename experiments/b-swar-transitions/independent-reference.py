#!/usr/bin/env python3
from pathlib import Path
import tempfile, subprocess, random, os, sys, hashlib
repo=Path(__file__).resolve().parents[2]
src=(repo/'experiments/b-swar-transitions/transitions.rs').read_text()
needle='let nthreads = thread::available_parallelism().map_or(4, |n| n.get());'
assert src.count(needle)==1
words=['a','z','a0','0a','a'*7,'a'*8,'a'*9,'a'*15,'a'*16,'a'*17,'a'*23,'a'*24,'a'*25,'a'*31,'a'*32,'0','9','00','7','not','and','or','z9z']
seps=[' ','-','_','.',',','/','"',"'",'€','é','😀','\x00','\x7f','[',']','@',':',';','`','{','~']
rng=random.Random(901704)
with tempfile.TemporaryDirectory(prefix='bt-independent-') as tmp:
 root=Path(tmp); bins=[]
 for n in (1,2,7,16):
  f=root/f'w{n}.rs'; f.write_text(src.replace(needle,f'let nthreads = {n};')); binary=root/f'w{n}'
  subprocess.run(['rustc','--edition=2021','-O','-C','overflow-checks=yes',str(f),'-o',str(binary)],check=True);bins.append(binary)
 for seed in range(48):
  d=root/f'd{seed}';o=root/f'ref{seed}';d.mkdir();o.mkdir()
  docs=[]
  for j in range(seed%13):
   chunks=[]
   for k in range(rng.randrange(0,80)):
    w=rng.choice(words);w=''.join(c.upper() if rng.randrange(2) else c for c in w)
    chunks.append(rng.choice(seps)+w+rng.choice(seps))
   text=''.join(chunks)
   if j==0: text+=''.join('!'*pad+('A'*n)+'?' for pad in range(9) for n in (1,7,8,9,15,16,17,23,24,25,31,32))
   docs.append(f'{j}\t{text}\n')
  (d/'docs.txt').write_bytes(''.join(docs).encode())
  queries=[]
  for w in words:queries.append('BOOL '+w)
  for i in range(150):
   a,b,c=[rng.choice(words) for _ in range(3)]
   queries.append(rng.choice([f'BOOL {a} AND {b} NOT {c}',f'BOOL {a} OR {b} AND {c}',f'PHRASE "{a} {b}"',f'PHRASE "{a} {a} {b}"']))
  (d/'queries.txt').write_text('\n'.join(queries)+'\n')
  subprocess.run([sys.executable,str(repo/'official/reference/b_index.py'),'--data',str(d),'--out',str(o)],check=True,stdout=subprocess.DEVNULL)
  expected=(o/'results.txt').read_bytes()
  for n,binary in zip((1,2,7,16),bins):
   out=root/f'o{seed}-{n}';out.mkdir();env=dict(os.environ,SD_DATA=str(d),SD_OUT=str(out))
   subprocess.run([str(binary)],check=True,env=env,stdout=subprocess.DEVNULL)
   got=(out/'results.txt').read_bytes()
   if got!=expected:raise SystemExit(f'FAIL seed={seed} threads={n} expected={hashlib.sha256(expected).hexdigest()} got={hashlib.sha256(got).hexdigest()}')
 print('PASS 48 corpora x 4 worker counts, mixed printable ASCII and UTF-8 separators, 8-byte boundary token lengths and random Boolean/phrase queries')
