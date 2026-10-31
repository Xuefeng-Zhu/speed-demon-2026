#!/usr/bin/env python3
"""Test-only injected allocation failures; no selected-source or environment mutation."""
from pathlib import Path
import hashlib,os,subprocess,tempfile
HERE=Path(__file__).resolve().parent
s=(HERE/'candidate.rs').read_text()
assert hashlib.sha256(s.encode()).hexdigest()=='77f764359aa3189f73e37d2b411ba80a700ee66ee25a40c0286e658ab45f52d4'
marker='fn loader_vec<T>(used: &AtomicUsize, n: usize) -> Option<Vec<T>> {'
assert s.count(marker)==1
s=s.replace(marker,'''static TEST_ALLOC_CALLS: AtomicUsize = AtomicUsize::new(0);
fn loader_vec<T>(used: &AtomicUsize, n: usize) -> Option<Vec<T>> {
    let at = std::env::var("SD_TEST_FAIL_AT").unwrap().parse::<usize>().unwrap();
    if TEST_ALLOC_CALLS.fetch_add(1, Relaxed) == at { eprintln!("GUARD_INJECT"); return None; }''',1)
s=s.replace('Some(graphs) => graphs,','Some(graphs) => { eprintln!("GUARD_FAST"); graphs },',1)
s=s.replace('None => load_graph_exact(path, threads),','None => { eprintln!("GUARD_FALLBACK"); load_graph_exact(path, threads) },',1)
needle='let threads = thread::available_parallelism().map_or(1, |n| n.get()).min(12);'
assert s.count(needle)==1
s=s.replace(needle,'let threads = std::env::var("SD_TEST_THREADS").unwrap().parse::<usize>().unwrap();',1)
with tempfile.TemporaryDirectory(prefix='d-guard-fault-') as tmp:
 t=Path(tmp); data=t/'data';out=t/'out';data.mkdir();out.mkdir()
 (data/'graph.txt').write_text('3 200\n'+'0 1 1\n'*199+'1 2 1\n')
 (data/'queries.txt').write_text('0 2\n2 0\n0 0\n')
 src=t/'test.rs';binary=t/'test';src.write_text(s)
 subprocess.run(['rustc','--edition=2021','-O','-C','overflow-checks=yes','-C','debug-assertions=yes',str(src),'-o',str(binary)],check=True)
 for threads in (1,2,7,12):
  total=threads*(3+2*threads)
  for fail in sorted({0,min(3,total-1),min(4*threads,total-1)}):
   env={**os.environ,'SD_DATA':str(data),'SD_OUT':str(out),'SD_TEST_THREADS':str(threads),'SD_TEST_FAIL_AT':str(fail)}
   r=subprocess.run([str(binary)],env=env,text=True,capture_output=True,timeout=30,check=True)
   assert 'GUARD_INJECT' in r.stderr and 'GUARD_FALLBACK' in r.stderr,(threads,fail,r.stderr)
   assert (out/'distances.txt').read_text()=='2\n-1\n0\n',(threads,fail)
   print('PASS threads',threads,'allocation failure',fail)
