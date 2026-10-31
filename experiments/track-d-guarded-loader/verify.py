#!/usr/bin/env python3
"""Verify fast-path/fallback selection and exact graph answers; temp files only."""
from pathlib import Path
import os, subprocess, tempfile
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
s= (HERE/'candidate.rs').read_text()
marker='const LOADER_BUDGET_BYTES: usize = 320 * 1024 * 1024;'
cap='let cap = m / threads / threads * 9 / 8 + 64;'
assert s.count(marker)==1 and s.count(cap)==1
s=s.replace('Some(graphs) => graphs,','Some(graphs) => { eprintln!("GUARD_FAST"); graphs },',1)
s=s.replace('None => load_graph_exact(path, threads),','None => { eprintln!("GUARD_FALLBACK"); load_graph_exact(path, threads) },',1)
with tempfile.TemporaryDirectory(prefix='d-loader-guard-test-') as tmp:
 t=Path(tmp); data=t/'data';out=t/'out';data.mkdir();out.mkdir()
 (data/'graph.txt').write_text('3 200\n' + '0 1 1\n'*199 + '1 2 1\n')
 (data/'queries.txt').write_text('0 2\n2 0\n0 0\n')
 for name,source,expected in [
   ('normal',s,'GUARD_FAST'),
   ('budget0',s.replace(marker,'const LOADER_BUDGET_BYTES: usize = 0;'),'GUARD_FALLBACK'),
   ('budget1',s.replace(marker,'const LOADER_BUDGET_BYTES: usize = 1;'),'GUARD_FALLBACK'),
   ('cap0',s.replace(cap,'let cap = 0;',1),'GUARD_FALLBACK'),
   ('cap1',s.replace(cap,'let cap = 1;',1),'GUARD_FALLBACK')]:
  src=t/(name+'.rs');binary=t/name;src.write_text(source)
  subprocess.run(['rustc','--edition=2021','-O','-C','overflow-checks=yes','-C','debug-assertions=yes',str(src),'-o',str(binary)],check=True)
  result=subprocess.run([str(binary)],env={**os.environ,'SD_DATA':str(data),'SD_OUT':str(out)},capture_output=True,text=True,check=True)
  assert expected in result.stderr,(name,result.stderr)
  assert (out/'distances.txt').read_text()=='2\n-1\n0\n',name
  print('PASS',name,expected)
 print('PASS forced budget and bucket fallback exact answers')
