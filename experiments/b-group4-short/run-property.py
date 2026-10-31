#!/usr/bin/env python3
"""Compile exact grouped-lookup source with optional forced short-hash collisions."""
from pathlib import Path
import subprocess, tempfile, sys, platform
root = Path(__file__).resolve().parents[2]
source = (root/'experiments/b-group4-short/candidate.rs').read_text()
testfile = (root/'experiments/b-short-lookup/candidate-property.rs').read_text()
tail = testfile[testfile.index('#[cfg(test)]\nmod independent'):] + (root/'experiments/b-group4-short/guard-tail.rs').read_text()
flags = ['-C', 'target-cpu=x86-64-v3'] if '--x86-v3' in sys.argv[1:] else []
if flags and (platform.system() != 'Linux' or platform.machine() not in ('x86_64','amd64')):
    raise SystemExit('--x86-v3 must run on Linux x86-64')
tail += '\n#[cfg(test)] mod independent_group { use super::*;\n' + (root/'experiments/b-group4-short/independent-tail.rs').read_text() + '\n#[test] fn test_independent_group() { main(); }\n}\n'
needle = '''    fn short_hash(mut x: u64) -> usize {
        x ^= x >> 30;
        x = x.wrapping_mul(0xbf58_476d_1ce4_e5b9);
        x ^= x >> 27;
        x = x.wrapping_mul(0x94d0_49bb_1331_11eb);
        ((x ^ (x >> 31)) >> 32) as usize
    }'''
assert source.count(needle) == 1
with tempfile.TemporaryDirectory() as d:
    for forced in (False, True):
        text = source
        test = tail
        if forced:
            text = text.replace(needle, '    fn short_hash(_x: u64) -> usize { 0 }')
            test = test.replace('run(100000)', 'run(5000)')
        p = Path(d)/('forced.rs' if forced else 'normal.rs')
        binary = p.with_suffix('')
        p.write_text(text+'\n'+test)
        subprocess.run(['rustc','--edition=2021','--test','-O','-C','overflow-checks=yes',*flags,str(p),'-o',str(binary)],check=True)
        result=subprocess.run([str(binary),'--nocapture'],check=True,text=True,capture_output=True)
        print(result.stdout)
        if flags and 'avx2_guard::group_load_at_protected_page_edges ... ok' not in result.stdout:
            raise SystemExit('AVX2 guard test did not run')
