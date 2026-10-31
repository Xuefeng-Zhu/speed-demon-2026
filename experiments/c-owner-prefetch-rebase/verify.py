#!/usr/bin/env python3
"""Check portable reference behavior and actual target x86 guard behavior."""
import argparse,hashlib,platform,subprocess,sys,tempfile
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--avx2',action='store_true');p.add_argument('--seeds',type=int,default=24);a=p.parse_args()
here=Path(__file__).resolve().parent
names=('ahead1','ahead4','ahead8','ahead4_cache')
if a.avx2:
 assert platform.machine() in ('x86_64','amd64'), 'AVX2 requires actual x86-64'
 features=Path('/proc/cpuinfo').read_text().lower(); assert 'avx2' in features, 'AVX2 CPU feature required'
flags=['-C','target-cpu=x86-64-v3'] if a.avx2 else []
needle='let (name, name_len, h) = field_name_hash(recs, &mut p);'
with tempfile.TemporaryDirectory(prefix='c-prefetch-verify-') as t:
 t=Path(t)
 for name in names:
  src=(here/f'{name}.rs').read_text(); print(name,hashlib.sha256(src.encode()).hexdigest(),flush=True)
  test=t/f'{name}-test.rs';test.write_text(src+'\n'+(here/'guard-tail.rs').read_text())
  subprocess.run(['rustc','--edition=2021','--test','-O','-C','overflow-checks=yes','-C','debug-assertions=yes',*flags,str(test),'-o',str(t/name)],check=True)
  subprocess.run([str(t/name)],check=True,timeout=60)
  args=[sys.executable,str(here/'reference.py'),'--source',str(here/f'{name}.rs'),'--seeds',str(a.seeds)]
  if a.avx2:args+=['--avx2']
  subprocess.run(args,check=True)
  assert src.count(needle)==1
  forced=t/f'{name}-forced.rs';forced.write_text(src.replace(needle,'let (name, name_len, _h) = field_name_hash(recs, &mut p); let h = 0u64;'))
  args=[sys.executable,str(here/'reference.py'),'--source',str(forced),'--seeds','8']
  if a.avx2:args+=['--avx2']
  subprocess.run(args,check=True)
print('PASS all variants: slice boundaries, mixed references, and forced-hash references')
