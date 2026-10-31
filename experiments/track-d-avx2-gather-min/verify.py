#!/usr/bin/env python3
"""Exercise the actual AVX2 path, scalar fallback, graph oracles, and mmap guards on Linux x86-64."""
import argparse, hashlib, os, pathlib, platform, shutil, subprocess, tempfile

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--extremes', action='store_true', help='also generate and test the full-size maximum-weight chain')
a=p.parse_args()
root=pathlib.Path(__file__).resolve().parent
src=root/'meeting.rs'; tail=root/'property-tail.rs'
expected='8d57095daa927d5e9f309c38d897d7ee0b771f29b54d06e873b05e45ff126772'
assert hashlib.sha256(src.read_bytes()).hexdigest()==expected, 'candidate source changed'
assert platform.system()=='Linux' and platform.machine().lower() in ('x86_64','amd64'), 'Linux x86-64 required'
cpu=pathlib.Path('/proc/cpuinfo').read_text().lower()
flags=set(next(line.split(':',1)[1].split() for line in cpu.splitlines() if line.startswith('flags')))
needed={'avx2','bmi1','bmi2','f16c','fma','movbe','popcnt','sse4_1','sse4_2','xsave'}
assert needed<=flags, f'x86-64-v3 features missing: {sorted(needed-flags)}'
assert 'abm' in flags or 'lzcnt' in flags, 'LZCNT/ABM flag missing'

def run(*args):
 print('+',*map(str,args),flush=True); subprocess.run([str(x) for x in args],check=True)
with tempfile.TemporaryDirectory(prefix='d-avx2-gather-verify-') as d:
 d=pathlib.Path(d); test=d/'test.rs'; test.write_bytes(src.read_bytes()+b'\n'+tail.read_bytes())
 for name,target in [('generic','x86-64'),('avx2','x86-64-v3')]:
  testbin=d/('test-'+name); mainbin=d/('main-'+name)
  flags=['--edition=2021','-O','-C','overflow-checks=yes','-C','debug-assertions=yes','-C',f'target-cpu={target}']
  run('rustc',*flags,'--test',test,'-o',testbin)
  if name=='avx2':
   objdump=shutil.which('objdump')
   if not objdump: raise RuntimeError('objdump required to verify gather code generation')
   asm=subprocess.check_output([objdump,'-d',str(testbin)],text=True)
   assert 'vpgatherqq' in asm, 'AVX2 gather instruction not found in test binary'
   print('PASS actual x86 AVX2 gather instruction present',flush=True)
  run(testbin)
  run('rustc',*flags,src,'-o',mainbin)
  for script in ['oracle.py','exhaustive.py','boundaries.py']:
   run('python3',root/script,mainbin)
  if a.extremes: run('python3',root/'extremes.py',mainbin)
print('PASS both generic and AVX2 builds; target timing still separate')
