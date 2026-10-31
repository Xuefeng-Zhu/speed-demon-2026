#!/usr/bin/env python3
"""Compare exact binaries and official reference on empty and length-boundary cases."""
import os,subprocess,sys,tempfile
from pathlib import Path
root=Path(__file__).resolve().parents[2]; ref=root/'official/reference/b_index.py'
binaries=[Path(x).resolve(strict=True) for x in sys.argv[1:]]
if not binaries: raise SystemExit('usage: small-fixtures.py BASELINE CANDIDATE [FORCED]')
cases=[
 (b'', b''),
 (b'0\t\n1\t!\n',b''),
 (b'',b'BOOL a\nPHRASE "a b"\n'),
 (b'0\tA aB aBc aBcD aBcDe abcdefg abcdefgh abcdefghi abcdefghijklmnopqrstuvwxyz123456\n1\t0 09 7p0z ZZzz\n2\t\n',
  b'BOOL a\nBOOL ab AND abcd\nBOOL abcde OR abcdefg\nBOOL abcdefgh NOT abcdefghi\nBOOL absent OR 7p0z\nPHRASE "abc abcd"\nPHRASE "abcdefgh abcdefghi"\n')]
with tempfile.TemporaryDirectory(prefix='b-pext-small-') as temp:
 rootdir=Path(temp)
 for i,(docs,queries) in enumerate(cases):
  d=rootdir/f'd{i}';r=rootdir/f'r{i}';d.mkdir();r.mkdir();(d/'docs.txt').write_bytes(docs);(d/'queries.txt').write_bytes(queries)
  subprocess.run([sys.executable,str(ref),'--data',str(d),'--out',str(r)],check=True)
  expected=(r/'results.txt').read_bytes()
  for j,binary in enumerate(binaries):
   o=rootdir/f'o{i}-{j}';o.mkdir();subprocess.run([str(binary)],env={**os.environ,'SD_DATA':str(d),'SD_OUT':str(o)},check=True)
   assert (o/'results.txt').read_bytes()==expected,(i,binary)
 print(f'PASS {len(cases)} empty/short/length fixtures for {len(binaries)} binaries')
