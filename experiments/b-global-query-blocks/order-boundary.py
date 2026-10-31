#!/usr/bin/env python3
"""Check dynamic query-block edges, query order and empty input vs reference."""
import argparse, os, subprocess, tempfile
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--binary',required=True);p.add_argument('--reference',required=True);a=p.parse_args();exe=str(Path(a.binary).resolve());ref=str(Path(a.reference).resolve())
with tempfile.TemporaryDirectory(prefix='b-query-block-edge-') as d:
 root=Path(d);data=root/'data';out=root/'out';expected=root/'ref'
 for x in (data,out,expected):x.mkdir()
 docs=[f'tag{i} '+['', 'a b a b', 'A — b', 'c c', 'a c a', 'b'][i%6] for i in range(65)]
 (data/'docs.txt').write_text(''.join(f'{i}\t{x}\n' for i,x in enumerate(docs)))
 patterns=['BOOL a AND b','BOOL a OR c NOT b','BOOL never AND a OR b','PHRASE "a b"','PHRASE "a a"','BOOL a AND never NOT c','PHRASE "a b"','BOOL b OR a AND c']
 def query(i):
  # The period 65 does not divide 256, so exchanging complete blocks changes results.
  return patterns[i%len(patterns)] if i%5==0 else f'BOOL tag{i%65}'
 for n in (0,1,2,255,256,257,511,512,513,1001):
  (data/'queries.txt').write_text(''.join(query(i)+'\n' for i in range(n)))
  subprocess.run(['python3',ref,'--data',str(data),'--out',str(expected)],check=True,stdout=subprocess.DEVNULL)
  subprocess.run([exe],env={**os.environ,'SD_DATA':str(data),'SD_OUT':str(out)},check=True)
  want=(expected/'results.txt').read_bytes()
  assert (out/'results.txt').read_bytes()==want,n
  if n>=512:
   lines=want.splitlines(keepends=True);swapped=b''.join(lines[256:512]+lines[:256]+lines[512:]);assert swapped!=want,'fixture fails to distinguish swapped query blocks'
  print('PASS queries',n,flush=True)
