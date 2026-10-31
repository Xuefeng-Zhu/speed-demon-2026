import hashlib,random,subprocess,sys,tempfile
from pathlib import Path
exe=Path(sys.argv[1]).resolve(); reference=Path('official/reference/b_index.py').resolve(); rnd=random.Random(8842)
for n in (63,64,65,2047,2048,2049,4095,4096,4097,8193):
 with tempfile.TemporaryDirectory(prefix='dense-bitmaps-') as t:
  p=Path(t); data=p/'data';ref=p/'ref';data.mkdir();ref.mkdir()
  with (data/'docs.txt').open('w') as f:
   for d in range(n):
    tokens=['all']+(['even'] if d%2==0 else [])+(['third'] if d%3==0 else [])+(['last'] if d==n-1 else [])+(['few'] if d%1024==0 else [])
    f.write(str(d)+'\t'+' '.join(tokens)+'\n')
  terms=['all','even','third','last','few','absent'];queries=[]
  for i in range(250):
   chosen=[rnd.choice(terms) for _ in range(rnd.randrange(1,7))]; q='BOOL '+chosen[0]+''.join(' '+rnd.choice(['AND','OR','NOT'])+' '+x for x in chosen[1:]);queries.append(q)
  queries+=['PHRASE "all even"','PHRASE "all even"','BOOL all NOT all','BOOL all OR absent AND even']
  (data/'queries.txt').write_text('\n'.join(queries)+'\n')
  subprocess.run([sys.executable,str(reference),'--data',str(data),'--out',str(ref)],check=True)
  subprocess.run([str(exe),str(data/'docs.txt'),str(data/'queries.txt'),str(p/'out')],check=True)
  actual=(p/'out').read_bytes();assert actual==(ref/'results.txt').read_bytes(),n
  print('PASS',n,hashlib.sha256(actual).hexdigest(),flush=True)
