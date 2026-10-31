import itertools,subprocess,tempfile,sys,hashlib
from pathlib import Path
candidate=Path(sys.argv[1]).resolve(); reference=Path('official/reference/b_index.py').resolve()
with tempfile.TemporaryDirectory(prefix='bitmap-independent-') as tmp:
 p=Path(tmp);d=p/'data';r=p/'ref';d.mkdir();r.mkdir()
 with (d/'docs.txt').open('w') as f:
  for n in range(2050):
   terms=['all']
   if n<2048: terms.append('common')
   if n%2==0: terms.append('even')
   if n in (0,62,63,64,65,2047,2048,2049): terms.append('edge')
   if n==2049: terms.append('last')
   f.write(str(n)+'\t'+' '.join(terms)+'\n')
 vocab=['all','common','even','edge','last','absent']; ops=['AND','OR','NOT']
 qs=['BOOL '+a+' '+op1+' '+b+' '+op2+' '+c for a,b,c in itertools.product(vocab,repeat=3) for op1,op2 in itertools.product(ops,repeat=2)]
 qs+=['BOOL '+a for a in vocab]+['PHRASE "all common"']*10
 (d/'queries.txt').write_text('\n'.join(qs)+'\n')
 subprocess.run([sys.executable,str(reference),'--data',str(d),'--out',str(r)],check=True)
 subprocess.run([str(candidate),str(d/'docs.txt'),str(d/'queries.txt'),str(p/'actual')],check=True)
 actual=(p/'actual').read_bytes();assert actual==(r/'results.txt').read_bytes();print('PASS',len(qs),'queries 2050 docs',hashlib.sha256(actual).hexdigest())
