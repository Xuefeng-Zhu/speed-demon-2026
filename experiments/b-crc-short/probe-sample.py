#!/usr/bin/env python3
"""Compare hash-table probe distributions for generated B inputs, without outputs."""
import argparse, collections, re
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--data',type=Path,required=True);a=p.parse_args()
queries=(a.data/'queries.txt').read_bytes().splitlines();terms=[];seen=set()
for q in queries:
 w=q.replace(b'"',b'').split();ts=w[1::2] if w[0]==b'BOOL' else w[1:]
 for x in ts:
  if len(x)<=8 and x not in seen:terms.append(x);seen.add(x)
size=1<<(max(len(terms)*2,1)-1).bit_length();mask=size-1
lut=[]
for n in range(256):
 c=n
 for _ in range(8):c=(c>>1)^(0x82f63b78 if c&1 else 0)
 lut.append(c)
def crc(x):
 z=0
 for n in range(8):z=(z>>8)^lut[(z^(x>>(n*8)))&255]
 return z
def orig(x):
 x^=x>>30;x=x*0xbf58476d1ce4e5b9&((1<<64)-1);x^=x>>27;x=x*0x94d049bb133111eb&((1<<64)-1);return (x^(x>>31))>>32
with (a.data/'docs.txt').open('rb') as f:samples=re.findall(rb'[a-z0-9]+',f.read(1<<19).lower())
samples=[x for x in samples if len(x)<=8]
for name,fn in [('crc32c',crc),('selected',orig)]:
 slots=[None]*size;extra=0
 for t in terms:
  h=fn(int.from_bytes(t,'little'))&mask
  while slots[h] is not None:extra+=1;h=(h+1)&mask
  slots[h]=t
 longest=run=0
 for key in slots*2:
  run=0 if key is None else run+1;longest=max(longest,run)
 distribution=collections.Counter()
 for t in samples:
  h=fn(int.from_bytes(t,'little'))&mask;n=1
  while slots[h] is not None and slots[h]!=t:h=(h+1)&mask;n+=1
  distribution[n]+=1
 total=len(samples)
 print(name,'terms',len(terms),'slots',size,'max_occupied_run',longest,'insertion_extras',extra,'sample_tokens',total,'mean_probes',sum(n*c for n,c in distribution.items())/total if total else 0,'max_sample_probes',max(distribution,default=0))
