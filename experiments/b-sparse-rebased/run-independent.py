#!/usr/bin/env python3
"""Run independent exact-source B sparse algebra, cutoff and cap tests."""
import hashlib,os,subprocess,sys,tempfile
from pathlib import Path
repo=Path(__file__).resolve().parents[2];source=repo/'experiments/b-sparse-rebased'
expected={'baseline.rs':'322cc95ee08cf6d4abc5e1b52240753f66c7eaf89ab669cb6d72b0a8487dc458','threshold512.rs':'c2d41e1e001ad67d3b0a808ca65b3207fc528c34ba80bf308597d60cc5b361c4'}
for name,digest in expected.items():assert hashlib.sha256((source/name).read_bytes()).hexdigest()==digest,name
with tempfile.TemporaryDirectory(prefix='b-sparse-independent-') as td:
 td=Path(td);binaries={}
 needle='let nthreads = thread::available_parallelism().map_or(4, |n| n.get());'
 base=(source/'baseline.rs').read_text();candidate=(source/'threshold512.rs').read_text()
 assert base.count(needle)==candidate.count(needle)==1
 versions={'baseline':base.replace(needle,'let nthreads = 1;'),'normal':candidate.replace(needle,'let nthreads = 1;')}
 marker='if total <= 512 {';assert versions['normal'].count(marker)==1
 versions['always_sparse']=versions['normal'].replace(marker,'if total <= usize::MAX {')
 versions['always_bitmap']=versions['normal'].replace(marker,'if total == 0 && false {')
 for name,text in versions.items():
  src=td/(name+'.rs');exe=td/name;src.write_text(text)
  subprocess.run(['rustc','--edition=2021','-O','-C','overflow-checks=yes',str(src),'-o',str(exe)],check=True);binaries[name]=str(exe)
 subprocess.run([sys.executable,str(repo/'experiments/b-sparse-postings/cutoff-review.py'),binaries['baseline'],binaries['normal']],cwd=repo,check=True)
 for name in ('normal','always_sparse','always_bitmap'):
  env={**os.environ,'B_RUST_BINARY':binaries[name]}
  subprocess.run([sys.executable,str(repo/'experiments/b-boolean-clauses/algebra.py'),str(repo/'experiments/b-rust-positional-adapter.py')],cwd=repo,env=env,check=True)
subprocess.run([sys.executable,str(source/'caps-review.py'),str(source/'threshold512.rs'),str(repo/'official/reference/b_index.py')],cwd=repo,check=True)
