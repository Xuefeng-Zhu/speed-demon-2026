#!/usr/bin/env python3
"""Exercise B byte-split cuts, empty shards, exact LF cuts, and huge records."""
import random,subprocess,sys,tempfile,hashlib
from pathlib import Path
REFERENCE=Path(sys.argv[2]).resolve() if len(sys.argv)>2 else (Path.cwd()/'official/reference/b_index.py').resolve()
BINARY=Path(sys.argv[1]).resolve()
assert BINARY.is_file()
q=(['PHRASE "a b"','PHRASE "a a"','PHRASE "a a a"','PHRASE "alpha beta"','PHRASE "x y z"','PHRASE "alpha beta"','BOOL a','BOOL a NOT b OR c','BOOL alpha OR beta AND gamma','BOOL 0001 OR 1','BOOL q AND absent']*3)
case_summaries=[]
with tempfile.TemporaryDirectory(prefix='b-byte-review-') as base:
 root=Path(base)
 for case in range(70):
  rng=random.Random(case+42271)
  n=case if case<=40 else rng.randrange(1,101)
  rows=[]
  for i in range(n):
   words=['','a a a b a','a-b a b','ALPHA BETA gamma', 'x—y z','0001 1 q','a separator b a b','badcc']
   text=rng.choice(words)
   if case in (41,42,43,44):
    # One or more huge lines allow many cuts within the same record.
    if i in ({0} if case==41 else {n//2} if case==42 else {n-1} if case==43 else {0,n//2,n-1}):
     text='a a b'+('.'*(1_100_100+case))+' a b c'
   if case in (45,46,47,48):
    # Whole file sizes divisible by worker count and many exact boundaries.
    text=('a b x y z '+('.'*rng.randrange(0,20)))
   rows.append(str(i).encode()+b'\t'+text.encode()+b'\n')
  data=root/f'data-{case}'; ref=root/f'ref-{case}'; out=root/f'out-{case}'
  data.mkdir();ref.mkdir();out.mkdir();(data/'docs.txt').write_bytes(b''.join(rows));(data/'queries.txt').write_text('\n'.join(q)+'\n')
  subprocess.run([sys.executable,str(REFERENCE),'--data',str(data),'--out',str(ref)],check=True,stdout=subprocess.DEVNULL)
  subprocess.run([str(BINARY),str(data/'docs.txt'),str(data/'queries.txt'),str(out/'results.txt')],check=True,stdout=subprocess.DEVNULL)
  actual=(out/'results.txt').read_bytes();expected=(ref/'results.txt').read_bytes()
  if actual!=expected: raise SystemExit(f'FAIL case={case} n={n}')
  case_summaries.append(hashlib.sha256(actual).hexdigest())
print('PASS 70 byte-partition cases including empty/tiny shards, long records, UTF-8, phrase overlap and duplicate queries; aggregate',hashlib.sha256(''.join(case_summaries).encode()).hexdigest())
