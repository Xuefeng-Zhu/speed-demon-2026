#!/usr/bin/env python3
"""Compare SIMD tokenizer's program outputs at every 32-byte alignment."""
import os, random, subprocess, sys, tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[0]
if len(sys.argv)!=3: raise SystemExit('usage: alignment.py CANDIDATE OFFICIAL_REFERENCE')
binary=str(Path(sys.argv[1]).resolve());reference=str(Path(sys.argv[2]).resolve())
with tempfile.TemporaryDirectory(prefix='b-simd-align-') as tmp:
 root=Path(tmp); data=root/'data'; out=root/'out'; ref=root/'ref'
 for p in (data,out,ref): p.mkdir()
 lengths=(1,2,3,7,8,15,16,23,24,30,31,32)
 terms=['x'*n for n in lengths]+['a','b','and','not','or','007','7','y'*32]
 queries=[f'BOOL {t}' for t in terms]+[f'PHRASE "{a} {b}"' for a in terms for b in terms]+['BOOL a OR b NOT x','PHRASE "x x"']
 (data/'queries.txt').write_text('\n'.join(queries)+'\n')
 docs=[]
 for i in range(32*len(lengths)*8):
  shift=i%32; n=lengths[(i//32)%len(lengths)]; which=(i//(32*len(lengths)))%8
  sep=['-',', ','é','—','...',' ','__','/'][which]
  content='!'*shift+'A'+sep+('X'*n)+sep+'b '+('007 '*(i%3))+'AND x x '+('y'*32)
  docs.append(f'{i}\t{content}\n')
 (data/'docs.txt').write_text(''.join(docs),encoding='utf-8')
 subprocess.run([sys.executable,reference,'--data',str(data),'--out',str(ref)],check=True)
 subprocess.run([binary],env=dict(os.environ,SD_DATA=str(data),SD_OUT=str(out)),check=True)
 if (ref/'results.txt').read_bytes()!=(out/'results.txt').read_bytes():raise SystemExit('FAIL mismatch')
 print('PASS',len(docs),'documents x 32 alignments x token lengths 1..32 and eight separator styles')
