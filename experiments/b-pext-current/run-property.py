#!/usr/bin/env python3
"""Test exact B source with portable emulation or actual Linux x86-64-v3 BMI2."""
from pathlib import Path
import hashlib, platform, subprocess, tempfile, sys
root=Path(__file__).resolve().parents[2]
source=(root/'experiments/b-pext-current/candidate.rs').read_text()
assert hashlib.sha256(source.encode()).hexdigest() == 'b935f0bf613107ef3d2faa7e4bc81fb52da42ec9b52790538750c17f14aa3a83'
tests=(root/'experiments/b-short-lookup/candidate-property.rs').read_text()
tests=tests[tests.index('#[cfg(test)]\nmod independent'):]
tests += (root/'experiments/b-pext-current/direct-tail.rs').read_text()
for name in ('independent-index-tail.rs','independent-plan-tail.rs'):
    tail=(root/'experiments/b-pext-direct'/name).read_text()
    module='index_review' if name.startswith('independent-index') else 'plan_review'
    tests += f'\n#[cfg(test)] mod {module} {{ use super::*;\n' + tail + '\n#[test] fn independent_review() { main(); }\n}\n'
actual='--x86-v3' in sys.argv[1:]
if actual:
    if platform.system()!='Linux' or platform.machine() not in ('x86_64','amd64'):
        raise SystemExit('--x86-v3 requires Linux x86-64')
    flags_lines=[line for line in Path('/proc/cpuinfo').read_text().splitlines() if line.startswith('flags')]
    if not flags_lines: raise SystemExit('Cannot verify CPU features')
    required={'avx','avx2','bmi1','bmi2','cx16','f16c','fma','lahf_lm','movbe','popcnt','ssse3','sse4_1','sse4_2','xsave'}
    for line in flags_lines:
        flags_set=set(line.split(':',1)[1].split())
        missing=required-flags_set
        if not ({'pni','sse3'} & flags_set): missing.add('sse3/pni')
        if missing: raise SystemExit(f'CPU lacks required target features: {sorted(missing)}')
    # Linux reports LZCNT as abm (or sometimes lzcnt).
    if any(not ({'abm','lzcnt'} & set(line.split(':',1)[1].split())) for line in flags_lines):
        raise SystemExit('CPU lacks lzcnt/abm')
flags=['-C','target-cpu=x86-64-v3'] if actual else ['--cfg','b_portable_pext']
needle='''    fn short_hash(mut x: u64) -> usize {
        x ^= x >> 30;
        x = x.wrapping_mul(0xbf58_476d_1ce4_e5b9);
        x ^= x >> 27;
        x = x.wrapping_mul(0x94d0_49bb_1331_11eb);
        ((x ^ (x >> 31)) >> 32) as usize
    }'''
assert source.count(needle)==1
with tempfile.TemporaryDirectory() as tmp:
    for forced in (False,True):
        text=source.replace(needle,'    fn short_hash(_x: u64) -> usize { 0 }') if forced else source
        tail=tests.replace('run(100000)','run(5000)') if forced else tests
        path=Path(tmp)/('forced.rs' if forced else 'normal.rs'); binary=path.with_suffix('')
        path.write_text(text+'\n'+tail)
        subprocess.run(['rustc','--edition=2021','--test','-O','-C','overflow-checks=yes',*flags,str(path),'-o',str(binary)],check=True)
        result=subprocess.run([str(binary),'--nocapture'],check=True,text=True,capture_output=True)
        print(result.stdout)
        if actual and 'bmi2_guard::direct_lookup_at_protected_page_end ... ok' not in result.stdout:
            raise SystemExit('BMI2 protected-page test did not run')
        if 'direct_exact::exhaust_all_legal_four_byte_encodings ... ok' not in result.stdout:
            raise SystemExit('direct index exhaustive test did not run')
