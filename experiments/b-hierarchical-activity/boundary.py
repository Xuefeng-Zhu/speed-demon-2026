#!/usr/bin/env python3
"""Independent set oracle for bitmap/summary boundaries, cached and fallback paths."""
import os, pathlib, random, subprocess, sys, tempfile
r = random.Random(812044)
N = 8195
words = ['common','even','sparse','edge','none','alternate']
with tempfile.TemporaryDirectory(prefix='b-activity-') as tmp:
 p=pathlib.Path(tmp); data=p/'data'; out=p/'out'; data.mkdir(); out.mkdir()
 present=[]; lines=[]
 for doc in range(N):
  ts=[]
  if doc % 5: ts.append('common')
  if doc % 2 == 0: ts.append('even')
  if doc in (0,63,64,65,4095,4096,4097,8191,8192,8194): ts+=['sparse','sparse']
  if doc in (1,63,64,4095,4096,8192,8193): ts.append('edge')
  if doc % 7==0: ts.append('alternate')
  present.append(set(ts)); lines.append(f"{doc}\t{' '.join(ts)}\n")
 (data/'docs.txt').write_text(''.join(lines))
 queries=[]; result=[]
 ops=['AND','OR','NOT']
 for i in range(1000):
  terms=[r.choice(words) for _ in range(r.randrange(1,7))]; os_=[r.choice(ops) for _ in terms[1:]]
  queries.append('BOOL '+terms[0]+''.join(' '+op+' '+t for op,t in zip(os_,terms[1:]))+'\n')
  ids=[]
  for d,ts in enumerate(present):
   v=terms[0] in ts
   for op,t in zip(os_,terms[1:]):
    x=t in ts; v=(v and x) if op=='AND' else ((v or x) if op=='OR' else (v and not x))
   if v: ids.append(d)
  result.append(f'{len(ids)} {sum(ids)}'+''.join(' '+str(x) for x in ids[:10])+'\n')
 (data/'queries.txt').write_text(''.join(queries))
 for binary in sys.argv[1:]:
  subprocess.run([binary],check=True,env={**os.environ,'SD_DATA':str(data),'SD_OUT':str(out)})
  assert (out/'results.txt').read_text()==''.join(result),binary
print('PASS 1000 queries, 8195 documents, sparse/dense/summary boundaries')
