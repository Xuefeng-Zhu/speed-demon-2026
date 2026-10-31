import random,subprocess,tempfile,sys
from pathlib import Path
repo=Path('official/reference/b_index.py')
exe=sys.argv[1]
vocab=['a','b','c','and','not','or','x'*32,'007','7','z','rich','cafe','the','0','42']
seps=[' ','-','/','...','’','—','§','\u00a0','\u212a']
for seed in range(40):
 r=random.Random(seed)
 with tempfile.TemporaryDirectory(prefix='b-phrase-fuzz-') as tmp:
  root=Path(tmp); data=root/'data'; out=root/'out'; ref=root/'ref'
  for p in (data,out,ref):p.mkdir()
  lines=[]
  for i in range(r.randrange(1,151)):
   if i==0: tokens=['a']*20
   elif i==1: tokens=['a','b','a','b','a','b']
   else: tokens=[r.choice(vocab+['unknown','outside']) for _ in range(r.randrange(0,65))]
   parts=[]
   for t in tokens: parts.append(t.upper() if r.random()<.4 else t)
   text=''.join(t+(r.choice(seps) if j+1<len(parts) else '') for j,t in enumerate(parts))
   lines.append(f'{i}\t{text}\n')
  (data/'docs.txt').write_text(''.join(lines),encoding='utf-8')
  queries=[]
  for j in range(1000):
   terms=[r.choice(vocab) for _ in range(r.randrange(2,9))]
   if j%10==0: terms=['a']*r.randrange(2,9)
   if j%10==1: terms=['a','b','a','b']
   if r.random()<.65: q='PHRASE "'+' '.join(terms)+'"'
   else:
    terms=terms[:r.randrange(1,7)]; q='BOOL '+terms[0]+''.join(' '+r.choice(['AND','OR','NOT'])+' '+t for t in terms[1:])
   queries.append(q)
   if j%83==0:queries.append(q)
  (data/'queries.txt').write_text('\n'.join(queries)+'\n',encoding='ascii')
  subprocess.run([sys.executable,str(repo),'--data',str(data),'--out',str(ref)],check=True)
  subprocess.run([exe,str(data/'docs.txt'),str(data/'queries.txt'),str(out/'results.txt')],check=True)
  a=(ref/'results.txt').read_bytes();b=(out/'results.txt').read_bytes()
  if a!=b:
   aa=a.splitlines();bb=b.splitlines()
   for i,(x,y) in enumerate(zip(aa,bb)):
    if x!=y: print('FAIL',seed,i,queries[i],x,y);break
   raise SystemExit(1)
print('PASS 40 corpora with mixed ASCII/Unicode separators, case, repeated/overlapping phrases, operators, zero-padded words, absent terms, duplicate queries and 32-byte terms')
