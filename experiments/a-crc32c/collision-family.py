#!/usr/bin/env python3
"""Construct legal equal-length CRC32C collisions and check exact A output."""
import argparse, datetime, hashlib, os, pathlib, subprocess, tempfile, resource, time
p=argparse.ArgumentParser();p.add_argument('--binary',action='append',required=True);p.add_argument('--reference',required=True);p.add_argument('--count',type=int,default=5143);a=p.parse_args()
def crc_word(crc,w):
 for byte in w.to_bytes(8,'little'):
  crc ^= byte
  for _ in range(8): crc=(crc>>1) ^ (0x82f63b78 if crc&1 else 0)
 return crc
def h(name):
 crc=0; pos=0
 while len(name)-pos>=8:
  crc=crc_word(crc,int.from_bytes(name[pos:pos+8],'little')); pos+=8
 rem=name[pos:]; crc=crc_word(crc,int.from_bytes(rem,'little')^len(rem))
 return crc
base=b'/'+b'a'*64; orig=h(base); cols=[]
for i in range(64):
 x=bytearray(base); x[i+1]=ord('b'); cols.append(h(x)^orig)
basis={};kernel=[]
for i,col in enumerate(cols):
 v=col; combo=1<<i
 while v:
  lead=v.bit_length()-1
  if lead not in basis: basis[lead]=(v,combo);break
  q,m=basis[lead];v^=q;combo^=m
 if v==0:kernel.append(combo)
assert len(kernel)>=13 and a.count <= 1<<len(kernel)
names=[]
for n in range(a.count):
 mask=0
 for j,k in enumerate(kernel):
  if n>>j&1:mask ^= k
 x=bytearray(base)
 for i in range(64):
  if mask>>i&1:x[i+1]=ord('b')
 name=bytes(x); assert h(name)==orig; names.append(name)
assert len(set(names))==len(names)
with tempfile.TemporaryDirectory(prefix='a-crc-collisions-') as td:
 root=pathlib.Path(td);data=root/'data';out=root/'out';ref=root/'ref';data.mkdir();out.mkdir();ref.mkdir(); start=datetime.datetime(2026,10,30,18)
 with (data/'requests.log').open('wb') as f:
  for i,name in enumerate(names):
   dt=start+datetime.timedelta(hours=(i*37)%72,minutes=i%60,seconds=(i//60)%60,microseconds=(i*97)%1000000)
   f.write(f'{dt:%Y-%m-%dT%H:%M:%S.%fZ} GET '.encode()+name+f' {500 if i%3==0 else 200} {i}\n'.encode())
 subprocess.run(['python3',str(pathlib.Path(a.reference).resolve()),'--data',str(data),'--out',str(ref)],check=True);expected=(ref/'summary.txt').read_bytes()
 for exe in a.binary:
  for n in (1,2,7,12):
   before=resource.getrusage(resource.RUSAGE_CHILDREN); start=time.perf_counter()
   subprocess.run([str(pathlib.Path(exe).resolve())],env=dict(os.environ,SD_DATA=str(data),SD_OUT=str(out),SD_THREADS=str(n)),check=True)
   elapsed=time.perf_counter()-start; after=resource.getrusage(resource.RUSAGE_CHILDREN)
   assert (out/'summary.txt').read_bytes()==expected,(exe,n)
   print('PASS',exe,'workers',n,'wall',round(elapsed,4),'cpu',round((after.ru_utime+after.ru_stime)-(before.ru_utime+before.ru_stime),4),flush=True)
 print('count',len(names),'crc',f'{orig:08x}','sha256',hashlib.sha256(expected).hexdigest())
