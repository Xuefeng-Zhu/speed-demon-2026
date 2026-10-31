#!/usr/bin/env python3
import hashlib, os, random, subprocess, sys, tempfile
from pathlib import Path
repo=Path(__file__).resolve().parent
if not (repo/'official/reference/b_index.py').is_file():
 repo=Path(__file__).resolve().parents[2]
if len(sys.argv)<2: raise SystemExit('usage: review.py BINARY [BINARY...]')
with tempfile.TemporaryDirectory(prefix='b-avx2-independent-') as tmp:
 root=Path(tmp); data=root/'data'; ref=root/'reference';data.mkdir();ref.mkdir()
 docs=[]
 for lead in range(96):
  for size in range(1,33):
   # Leading separators align the token to every lane; A/a distinguish case handling.
   text=b'!'*lead + (b'A' if lead%2 else b'a')*size + b'@' + b'Case No. 007-1234 / x x '
   if (lead+size)%3==0:text+=b'Z\xc3\xbcrich \xf0\x9d\x94\x84'
   if (lead+size)%5==0:text+=b' ' + b'b'*32
   docs.append(text)
 for n in [0,1,31,32,33,63,64,65,95,96,97,127,128,129,1023,1048575]:
  docs.extend([b'!'*n,b'A'*n,b'?'*n+b'0'*32+b'!'])
 rng=random.Random(849302)
 alphabet=[b'a',b'Z',b'0',b'9',b'!',b'.',b'/',b' ',b'-',b'\xc3\xa9',b'\xf0\x9d\x94\x84']
 for _ in range(1000):docs.append(b''.join(rng.choice(alphabet) for _ in range(rng.randrange(0,160))))
 with (data/'docs.txt').open('wb') as out:
  for i,text in enumerate(docs):out.write(str(i).encode()+b'\t'+text+b'\n')
 queries=[f'BOOL {"a"*n}' for n in range(1,33)]
 queries += [f'PHRASE "{"a"*n} case"' for n in range(1,33)]
 queries += ['BOOL case OR 007 NOT 1234','BOOL x','PHRASE "x x"','BOOL bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb','BOOL rich','BOOL 000','PHRASE "case no"']
 queries += ['BOOL '+('0'*n) for n in range(1,33)]
 (data/'queries.txt').write_text('\n'.join(queries)+'\n',encoding='ascii')
 subprocess.run([sys.executable,str(repo/'official/reference/b_index.py'),'--data',str(data),'--out',str(ref)],check=True)
 expected=(ref/'results.txt').read_bytes()
 for idx,binary in enumerate(sys.argv[1:]):
  out=root/f'out{idx}';out.mkdir(); env=dict(os.environ,SD_DATA=str(data),SD_OUT=str(out));subprocess.run([str(Path(binary).resolve())],env=env,check=True)
  got=(out/'results.txt').read_bytes()
  if got!=expected:raise SystemExit(f'FAIL {binary}')
 print('PASS',len(docs),'documents',len(queries),'queries',hashlib.sha256(expected).hexdigest())
