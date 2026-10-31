from pathlib import Path
import argparse, tempfile, subprocess, sys, random
parser=argparse.ArgumentParser()
parser.add_argument('candidate', type=Path, help='compiled candidate executable')
args=parser.parse_args()
exe=str(args.candidate.resolve()); ref=Path('official/reference/b_index.py').resolve(); tested=0
for n in list(range(0,31))+[35,36,37,63,64,65,80,81,82,89,90,91,99,100,101,179,180,181]:
 rng=random.Random(n+551)
 with tempfile.TemporaryDirectory(prefix='b9shards-') as tmp:
  p=Path(tmp); data=p/'data'; out=p/'out'; reference=p/'ref'
  data.mkdir();out.mkdir();reference.mkdir()
  docs=[]
  for i in range(n):
   terms=['a','a','a','b','a'] if i%3!=1 else ['a','b','c','a','b','c']
   if i%11==0: terms=[]
   if i%7==0: terms+=['x'*32,'007','00','000']
   if rng.randrange(3)==0: terms+=['A','B','A','b']
   docs.append(str(i)+'\t'+' — '.join(terms)+'\n')
  (data/'docs.txt').write_text(''.join(docs))
  queries=['PHRASE "a a"']*30+['PHRASE "a a a"','PHRASE "a b a"','PHRASE "a b c"','PHRASE "007 00"','BOOL a OR b NOT c','BOOL '+('x'*32),'BOOL a','BOOL a AND c']
  (data/'queries.txt').write_text('\n'.join(queries)+'\n')
  subprocess.run([sys.executable,str(ref),'--data',str(data),'--out',str(reference)],check=True,stdout=subprocess.DEVNULL)
  subprocess.run([exe,str(data/'docs.txt'),str(data/'queries.txt'),str(out/'results.txt')],check=True)
  a=(out/'results.txt').read_bytes(); b=(reference/'results.txt').read_bytes()
  if a!=b: raise AssertionError(f'N={n}')
  tested+=1
print('PASS nine-worker ASan/UBSan: '+str(tested)+' document-count/reference fixtures, including N<9 and adjacent 9-way shard boundaries')
