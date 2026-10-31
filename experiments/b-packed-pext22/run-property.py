#!/usr/bin/env python3
import argparse, pathlib, platform, subprocess, tempfile
p=argparse.ArgumentParser();p.add_argument('--x86-v3',action='store_true');a=p.parse_args()
root=pathlib.Path(__file__).resolve().parent
source=(root/'candidate.rs').read_text();tail=(root/'property-tail.rs').read_text()
original='''        x ^= x >> 30;
        x = x.wrapping_mul(0xbf58_476d_1ce4_e5b9);
        x ^= x >> 27;
        x = x.wrapping_mul(0x94d0_49bb_1331_11eb);
        ((x ^ (x >> 31)) >> 32) as usize'''
assert source.count(original)==1
if a.x86_v3:
 assert platform.machine() in ('x86_64','AMD64')
 flags=pathlib.Path('/proc/cpuinfo').read_text().lower();assert all(' '+x+' ' in ' '+flags.replace('\n',' ')+' ' for x in ('avx2','bmi2'))
 feature=['-C','target-cpu=x86-64-v3']
else: feature=['--cfg','pext_emulate']
with tempfile.TemporaryDirectory(prefix='b-pext-property-') as d:
 for label,body,filter_test in [('normal',source,None),('collision',source.replace(original,'        let _ = x; 0'), 'shared_seven_prefix_and_misses')]:
  path=pathlib.Path(d)/(label+'.rs');binary=pathlib.Path(d)/label;path.write_text(body+'\n'+tail)
  subprocess.run(['rustc','--edition=2021','--test','-O','-C','overflow-checks=yes',*feature,str(path),'-o',str(binary)],check=True)
  subprocess.run([str(binary),*([filter_test] if filter_test else [])],check=True)
print('normal/forced-collision exact properties passed:', 'actual x86 BMI2' if a.x86_v3 else 'portable emulation')
