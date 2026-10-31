import itertools,random,subprocess,tempfile,os,sys,hashlib
from pathlib import Path
repo=Path(__file__).resolve().parents[2]
ref=repo/'official/reference/b_index.py'
if len(sys.argv)!=3: raise SystemExit('usage: cutoff-review.py BASELINE CANDIDATE')
bins={'baseline':str(Path(sys.argv[1]).resolve()),'candidate':str(Path(sys.argv[2]).resolve())}
rng=random.Random(74129)
with tempfile.TemporaryDirectory(prefix='sparse-review-') as tmp:
 p=Path(tmp);data=p/'data';data.mkdir();refs=p/'ref';refs.mkdir()
 # Exact memberships: a=255, b=257, c=256; pair lengths 511/512/513.
 with (data/'docs.txt').open('w') as f:
  for i in range(1025):
   ts=[t for t,n in [('a',255),('b',257),('c',256),('d',512),('e',1),('f',0)] if i<n]
   ts += [f'm{i%64:02d}']
   f.write(f'{i}\t'+ ' '.join(ts)+'\n')
 terms=['a','b','c','d','e','f','none','m00','m01','m63']
 queries=[]
 for a,b in [('a','c'),('a','b'),('b','c'),('a','d')]:
  for op in ('AND','OR','NOT'):queries.append(f'BOOL {a} {op} {b}')
 for n in range(1,7):
  for ops in itertools.product(('AND','OR','NOT'),repeat=n-1):
   q='BOOL a'
   for op,t in zip(ops,itertools.cycle(('b','c','f','a','d'))):q+=f' {op} {t}'
   queries.append(q)
 for _ in range(5000):
  n=rng.randint(1,6);q='BOOL '+rng.choice(terms)
  for i in range(n-1):q+=' '+rng.choice(('AND','OR','NOT'))+' '+rng.choice(terms)
  queries.append(q)
 queries += ['PHRASE "a b"','PHRASE "a b"','PHRASE "a a"']
 (data/'queries.txt').write_text('\n'.join(queries)+'\n')
 subprocess.run([sys.executable,str(ref),'--data',str(data),'--out',str(refs)],check=True,stdout=subprocess.DEVNULL)
 expected=(refs/'results.txt').read_bytes()
 for name in ('baseline','candidate'):
  out=p/name;out.mkdir();env=dict(os.environ,SD_DATA=str(data),SD_OUT=str(out));subprocess.run([bins[name]],env=env,check=True)
  got=(out/'results.txt').read_bytes();assert got==expected,name
 print('PASS',len(queries),'queries; sparse cutoff 511/512/513, OR/AND/NOT, duplicates, SHA256',hashlib.sha256(expected).hexdigest())
