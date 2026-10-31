#!/usr/bin/env python3
import os,random,subprocess,sys,tempfile
from pathlib import Path

reference=Path(__file__).resolve().parents[2]/'official/reference/b_index.py'
binary=str(Path(sys.argv[1]).resolve()) if len(sys.argv)>1 else '/tmp/b-short-review-candidate'
rng=random.Random(1177009)
alphabet='abcxyz012789'
seps=[' ','-','.',',','/','_',':','é','—','😀']
terms=['a','aa','aaa','aaaaaaaa','aaaaaaaaa','0','00','00000000','z9z9z9z9']
terms += [''.join(rng.choice(alphabet) for _ in range(n)) for n in range(1,33)]
with tempfile.TemporaryDirectory(prefix='b-short-independent-') as tmp:
 root=Path(tmp)
 for case in range(90):
  data=root/f'data{case}';ref=root/f'ref{case}';out=root/f'out{case}'
  for p in (data,ref,out):p.mkdir()
  chosen=terms if case%3 else [t for t in terms if len(t)>8]
  docs=[]
  for i in range(case%19):
   words=[rng.choice(terms) for _ in range(rng.randrange(0,50))]
   text=''.join(rng.choice(seps)+''.join(c.upper() if rng.randrange(2) else c for c in w) for w in words)
   if i==0:text+=' '.join(terms)
   docs.append(f'{i}\t{text}\n')
  (data/'docs.txt').write_text(''.join(docs))
  qs=['BOOL '+w for w in chosen]
  for _ in range(120):
   a,b,c=(rng.choice(chosen) for _ in range(3))
   qs.append(rng.choice([f'BOOL {a} OR {b} NOT {c}',f'BOOL {a} AND {b} OR {c}',f'PHRASE "{a} {b}"',f'PHRASE "{a} {a} {b}"']))
  (data/'queries.txt').write_text('\n'.join(qs)+'\n')
  subprocess.run([sys.executable,str(reference),'--data',str(data),'--out',str(ref)],check=True,stdout=subprocess.DEVNULL)
  subprocess.run([binary],env=dict(os.environ,SD_DATA=str(data),SD_OUT=str(out)),check=True)
  if (ref/'results.txt').read_bytes()!=(out/'results.txt').read_bytes():raise SystemExit(f'mismatch case {case}')
print('PASS 90 independent reference corpora, including no short query terms and empty documents')
