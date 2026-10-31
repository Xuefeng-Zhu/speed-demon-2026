from pathlib import Path
import argparse,tempfile,subprocess,sys,random
parser=argparse.ArgumentParser()
parser.add_argument("candidate", help="path to compiled candidate")
args=parser.parse_args()
r=random.Random(827461)
with tempfile.TemporaryDirectory(prefix='b-bounded-random-') as d:
 root=Path(d);data=root/'data';ref=root/'ref';data.mkdir();ref.mkdir()
 tokens=['a','b','c','d','e','f','00','7','and','not','zonly']
 with (data/'docs.txt').open('w') as f:
  for doc in range(300):
   words=[r.choice(tokens) for _ in range(r.randrange(0,80))]
   if doc%7==0: words+=['a','a','a','a']
   f.write(f'{doc}\t'+' '.join(w.upper() if r.randrange(5)==0 else w for w in words)+'\n')
 queries=[]
 for j in range(10000):
  if j%7==0 and queries: queries.append(r.choice(queries))
  elif j%5==0: queries.append('BOOL '+r.choice(tokens)+' '+r.choice(['AND','OR','NOT'])+' '+r.choice(tokens+['absent']))
  else: queries.append('PHRASE "'+' '.join(r.choice(tokens+['absent']) for _ in range(r.randrange(2,9)))+'"')
 (data/'queries.txt').write_text('\n'.join(queries)+'\n')
 subprocess.run([sys.executable,'official/reference/b_index.py','--data',str(data),'--out',str(ref)],check=True)
 subprocess.run([args.candidate,str(data/'docs.txt'),str(data/'queries.txt'),str(root/'out')],check=True)
 assert (root/'out').read_bytes()==(ref/'results.txt').read_bytes()
 print('PASS 300 random documents; 10,000 mixed and duplicate queries against reference')
