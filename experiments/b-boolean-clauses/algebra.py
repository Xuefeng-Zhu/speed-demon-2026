import itertools,random,subprocess,sys,tempfile
from pathlib import Path
exe=Path(sys.argv[1]);r=random.Random(7042026); words=[f't{i}' for i in range(6)]
with tempfile.TemporaryDirectory() as d:
 p=Path(d);n=64
 (p/'docs.txt').write_text(''.join(f"{mask}\t{' '.join(t for i,t in enumerate(words) if mask>>i&1)}\n" for mask in range(n)))
 queries=[]
 for length in range(1,7):
  for ops in itertools.product(('AND','OR','NOT'),repeat=length-1):queries.append((list(range(length)),ops))
 for _ in range(5000):
  length=r.randrange(1,7);queries.append(([r.randrange(6) for _ in range(length)],tuple(r.choice(('AND','OR','NOT')) for i in range(length-1))))
 lines=[]; expected=[]
 for terms,ops in queries:
  lines.append('BOOL '+words[terms[0]]+''.join(' '+op+' '+words[t] for op,t in zip(ops,terms[1:]))+'\n')
  vals=[]
  for mask in range(n):
   result=bool(mask>>terms[0]&1)
   for op,t in zip(ops,terms[1:]):
    bit=bool(mask>>t&1)
    result=(result and bit) if op=='AND' else (result or bit) if op=='OR' else (result and not bit)
   if result:vals.append(mask)
  expected.append(f'{len(vals)} {sum(vals)}'+''.join(' '+str(v) for v in vals[:10])+'\n')
 (p/'queries.txt').write_text(''.join(lines));subprocess.run([str(exe),str(p/'docs.txt'),str(p/'queries.txt'),str(p/'out.txt')],check=True)
 assert (p/'out.txt').read_text()==''.join(expected)
 print('PASS',len(queries),'expressions x 64 membership assignments')
