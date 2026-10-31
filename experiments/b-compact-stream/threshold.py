#!/usr/bin/env python3
"""Cross BOOL u16/u32 sentinel threshold and compare exact reference results."""
import argparse, os, pathlib, subprocess, tempfile
p=argparse.ArgumentParser();p.add_argument('--binary',required=True);p.add_argument('--reference',required=True);p.add_argument('--trace');a=p.parse_args()
bin=str(pathlib.Path(a.binary).resolve());ref=str(pathlib.Path(a.reference).resolve());trace=str(pathlib.Path(a.trace).resolve()) if a.trace else None
with tempfile.TemporaryDirectory(prefix='b-stream-threshold-') as d:
 root=pathlib.Path(d);data=root/'data';actual=root/'actual';expect=root/'expect'
 for x in (data,actual,expect):x.mkdir()
 for n in (0,1,65534,65535,65536,65537):
  def word(i):return f'k{i:05d}'
  if n==0:
   queries=['PHRASE "a b"','PHRASE "a a"','PHRASE "a b"']
   docs=['a b a a', 'a A b', '', 'outside']
  else:
   terms=[word(i) for i in range(n)];queries=[]
   for j in range(0,n,3):
    q='BOOL '+terms[j]
    if j+1<n:q+=' OR '+terms[j+1]
    if j+2<n:q+=' NOT '+terms[j+2]
    queries.append(q)
   if n>1:
    queries+=['PHRASE "'+terms[0]+' '+terms[1]+'"','BOOL '+terms[0]+' AND '+terms[-1], 'BOOL '+terms[-1]+' OR '+terms[0]]
   docs=[terms[0]+' '+terms[min(n-1,1)]+' '+terms[-1],terms[-1]+' '+terms[0], '', 'outside']
  (data/'queries.txt').write_text('\n'.join(queries)+'\n',encoding='ascii')
  (data/'docs.txt').write_text(''.join(f'{i}\t{x}\n' for i,x in enumerate(docs)),encoding='ascii')
  subprocess.run(['python3',ref,'--data',str(data),'--out',str(expect)],check=True,stdout=subprocess.DEVNULL)
  env={**os.environ,'SD_DATA':str(data),'SD_OUT':str(actual)}
  subprocess.run([bin],env=env,check=True)
  assert (actual/'results.txt').read_bytes()==(expect/'results.txt').read_bytes(),f'n={n}'
  if trace:
   result=subprocess.run([trace],env=env,check=True,capture_output=True,text=True)
   want=f'STREAM bools={n} width={16 if n<=65535 else 32}'
   assert want in result.stderr,(want,result.stderr)
   assert (actual/'results.txt').read_bytes()==(expect/'results.txt').read_bytes()
  print('PASS bool_count',n,'reference',flush=True)
