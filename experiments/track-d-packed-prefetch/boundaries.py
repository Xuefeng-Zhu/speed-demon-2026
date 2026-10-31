#!/usr/bin/env python3
"""Boundary and fallback tests, no generated datasets retained."""
import os, pathlib, subprocess, sys, tempfile
binary = sys.argv[1]
with tempfile.TemporaryDirectory() as t:
 p=pathlib.Path(t); data=p/'data'; out=p/'out'; data.mkdir(); out.mkdir()
 for n in [2097152, 2097153]:
  weights=[0,1,2045,2046,2047,2048,4095,65535,2**31,2**32-1]
  edges=[(0,n-1,1000)]+[(n-1,i+1,w) for i,w in enumerate(weights)]
  edges += [(i+1,0,w) for i,w in enumerate(weights)]
  queries=[(n-1,i+1) for i in range(len(weights))]+[(0,n-1),(n-1,n-1)]
  expected=[str(w) for w in weights]+['1000','0']
  (data/'graph.txt').write_text(f'{n} {len(edges)}\n'+''.join(f'{u} {v} {w}\n' for u,v,w in edges))
  (data/'queries.txt').write_text(''.join(f'{u} {v}\n' for u,v in queries))
  subprocess.run([binary],check=True,env={**os.environ,'SD_DATA':str(data),'SD_OUT':str(out)})
  actual=(out/'distances.txt').read_text().splitlines()
  assert actual==expected,(n,expected,actual)
  print('PASS n=',n,'boundary weights, top node, short/wide graph mode')
