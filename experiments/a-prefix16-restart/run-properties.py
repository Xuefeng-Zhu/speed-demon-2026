#!/usr/bin/env python3
"""Compile exact candidate + two independent property suites, in release and checked modes."""
import argparse,platform,subprocess,tempfile
from pathlib import Path
root=Path(__file__).resolve().parent
p=argparse.ArgumentParser();p.add_argument('--generic',action='store_true');a=p.parse_args()
src='\n'.join((root/n).read_text() for n in ('candidate.rs','property-tail.rs','independent-tail.rs'))
with tempfile.TemporaryDirectory(prefix='a-prefix-props-') as t:
 t=Path(t);s=t/'tests.rs';s.write_text(src)
 flags=['rustc','--edition=2021','--test','-O','-Awarnings']
 if not a.generic and platform.machine().lower() in ('x86_64','amd64'):flags+=['-C','target-cpu=x86-64-v3']
 for checked in (False,True):
  exe=t/('checked' if checked else 'release')
  subprocess.run(flags+['-C',f'overflow-checks={"yes" if checked else "no"}',str(s),'-o',str(exe)],check=True)
  if checked:
   # The baseline latency SWAR intentionally wraps; checked tests either use
   # zero latency or test only hashing/rehashing, so its wrap is not exercised.
   for name in ('prefix_review::','independent::canonical_hash_boundaries_and_tail','independent::rehash_growth_preserves_ids'):
    subprocess.run([str(exe),name,'--nocapture'],check=True)
  else:subprocess.run([str(exe),'--nocapture'],check=True)
