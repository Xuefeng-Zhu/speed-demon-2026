#!/usr/bin/env python3
"""Compare B candidates on many distinct phrases sharing frequent bigrams."""
from pathlib import Path
from random import Random
import argparse,hashlib,subprocess,tempfile,time
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('baseline');p.add_argument('candidate');p.add_argument('--documents',type=int,default=100)
a=p.parse_args()
if a.documents<1:p.error('documents must be positive')
rng=Random(177);phrases=set()
while len(phrases)<19000:phrases.add(' '.join(rng.choices('abcdefghij',k=8)))
with tempfile.TemporaryDirectory(prefix='b-diverse-') as td:
 root=Path(td);docs=root/'docs.txt';queries=root/'queries.txt'
 docs.write_text(''.join(f'{i}\t'+('a b c d e f g h i j '*120)+'\n' for i in range(a.documents)))
 queries.write_text(''.join(f'PHRASE "{p}"\n' for p in sorted(phrases)))
 outputs=[]
 for label,exe in [('baseline',a.baseline),('candidate',a.candidate)]:
  output=root/(label+'.txt');started=time.monotonic();subprocess.run([exe,str(docs),str(queries),str(output)],check=True)
  b=output.read_bytes();outputs.append(b)
  print(label,'seconds',round(time.monotonic()-started,3),'sha256',hashlib.sha256(b).hexdigest(),flush=True)
 assert outputs[0]==outputs[1]
 print('PASS exact output on 19,000 unique phrases with repeated common document tokens')
