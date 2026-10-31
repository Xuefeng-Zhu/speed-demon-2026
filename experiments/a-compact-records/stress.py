#!/usr/bin/env python3
"""Reference-check compact/escaped A records and force local ID overflow."""
import argparse, datetime, os, pathlib, random, subprocess, tempfile
p=argparse.ArgumentParser();p.add_argument('--binary',required=True);p.add_argument('--reference',required=True);p.add_argument('--instrumented');a=p.parse_args()
binary=str(pathlib.Path(a.binary).resolve());ref=str(pathlib.Path(a.reference).resolve());instrumented=str(pathlib.Path(a.instrumented).resolve()) if a.instrumented else None
base=datetime.datetime(2026,10,30,18);modes=['GET','POST','OPTIONS','PUT','PATCH','HEAD','DELETE'];latencies=[0,1048573,1048574,1048575,1048576,4294967295,12345678];statuses=[100,200,499,500,501,599]
with tempfile.TemporaryDirectory(prefix='a-compact-stress-') as td:
 root=pathlib.Path(td);data=root/'data';actual=root/'actual';expected=root/'expected'
 for p in (data,actual,expected):p.mkdir()
 for case in ['empty','all_escape','alternating','id_boundaries']:
  out=[]
  n=0 if case=='empty' else (2422*36 if case=='id_boundaries' else 40000)
  for i in range(n):
   hour=(i*17+i//17)%72; when=base+datetime.timedelta(hours=hour,seconds=(i*379)%3600,microseconds=i%1000000)
   endpoint=f'/id/{i%2422:04}' if case=='id_boundaries' else f'/route/{i%29:02}'
   if case=='all_escape': lat=[1048575,1048576,4294967295,12345678][i%4]
   elif case=='alternating': lat=[0,1048575,1048574,4294967295][i%4]
   else: lat=latencies[(i//2422+i)%len(latencies)]
   out.append(when.strftime('%Y-%m-%dT%H:%M:%S.%fZ')+f' {modes[i%len(modes)]} {endpoint} {statuses[i%len(statuses)]} {lat}\n')
  (data/'requests.log').write_text(''.join(out),encoding='ascii')
  subprocess.run(['python3',ref,'--data',str(data),'--out',str(expected)],check=True,stdout=subprocess.DEVNULL)
  want=(expected/'summary.txt').read_bytes()
  for workers in (1,2,3,7,12,32):
   env={**os.environ,'SD_DATA':str(data),'SD_OUT':str(actual),'SD_THREADS':str(workers)}
   subprocess.run([binary],env=env,check=True)
   got=(actual/'summary.txt').read_bytes(); assert got==want,(case,workers)
   if case=='id_boundaries' and workers==1 and instrumented:
    r=subprocess.run([instrumented],env=env,check=True,capture_output=True,text=True)
    line=next(line for line in r.stderr.splitlines() if line.startswith('ESCAPE '))
    fields=dict(part.split('=') for part in line.split()[1:]); assert int(fields['id'])>0,fields
    assert (actual/'summary.txt').read_bytes()==want
    print('PASS local ID >=2048 reached',fields,flush=True)
  print('PASS',case,n,'records, workers 1/2/3/7/12/32',flush=True)
