#!/usr/bin/env python3
"""Verify reordered parse with long prefixes, collisions and compact escape boundaries."""
import argparse, datetime, os, random, subprocess, tempfile
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--baseline',required=True);p.add_argument('--candidate',required=True);p.add_argument('--forced-baseline',required=True);p.add_argument('--forced-candidate',required=True);p.add_argument('--reference',required=True);a=p.parse_args()
binaries={k: str(Path(getattr(a,k)).resolve(strict=True)) for k in ('baseline','candidate','forced_baseline','forced_candidate')}
reference=str(Path(a.reference).resolve(strict=True)); start=datetime.datetime(2026,10,30,18)
names=['/','/a','/ab','/abc']+[('/'+'x'*(i%121)+f'{i:04}') for i in range(2422)]
assert len(set(names))==2426 and min(map(len,names))==1 and max(map(len,names))==125
random.Random(8821).shuffle(names)
latencies=[0,1,1048573,1048574,1048575,1048576,4294967295]; statuses=[100,199,499,500,599]; methods=['GET','POST','PUT','PATCH','DELETE','HEAD','OPTIONS']
lines=[]
for i in range(11000):
 name=names[i] if i<len(names) else names[(i*997 + i//17)%len(names)]
 hour=(i*47+i//19)%72; date=start+datetime.timedelta(hours=hour,seconds=(i*719)%3600,microseconds=(i*101)%1000000)
 status=599 if i==2047 else statuses[i%len(statuses)];latency=1048574 if i==2047 else latencies[(i//7+i)%len(latencies)]
 lines.append(date.strftime('%Y-%m-%dT%H:%M:%S.%fZ')+f' {methods[i%len(methods)]} {name} {status} {latency}\n')
 if i in (2047,2048,4095):lines.append(lines[-1])
with tempfile.TemporaryDirectory(prefix='a-order-independent-') as td:
 root=Path(td); data=root/'data'; ref=root/'ref'; out=root/'out'
 for x in (data,ref,out):x.mkdir()
 (data/'requests.log').write_text(''.join(lines),encoding='ascii')
 subprocess.run(['python3',reference,'--data',str(data),'--out',str(ref)],check=True,stdout=subprocess.DEVNULL)
 want=(ref/'summary.txt').read_bytes()
 for threads in (1,2,7,12,32):
  for name,binary in binaries.items():
   env={**os.environ,'SD_DATA':str(data),'SD_OUT':str(out),'SD_THREADS':str(threads)}
   subprocess.run([binary],env=env,check=True,stdout=subprocess.DEVNULL)
   assert (out/'summary.txt').read_bytes()==want,(name,threads)
print('PASS 2426 endpoints covering every length 1–125, repeated/duplicate lines, status/latency boundaries, normal + forced collisions at 1/2/7/12/32 workers')
