#!/usr/bin/env python3
"""Verify rebased C rowcache with reference and independent collision tests."""
import argparse
from pathlib import Path
import subprocess
import sys
import tempfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
parser = argparse.ArgumentParser()
parser.add_argument('--avx2', action='store_true')
args = parser.parse_args()
flags = ['-C', 'target-cpu=x86-64-v3'] if args.avx2 else []
source = (HERE / 'rowcache.rs').read_text()

def run(*args):
    subprocess.run([str(a) for a in args], check=True)

with tempfile.TemporaryDirectory(prefix='c-rowcache-rebase-') as tmp:
    tmp = Path(tmp)
    run(sys.executable, HERE/'reference.py', '--source', HERE/'rowcache.rs', '--seeds', '24',
        *(['--avx2'] if args.avx2 else []))
    needle = 'let (name, name_len, h) = field_name_hash(recs, &mut p);'
    assert source.count(needle) == 1
    forced = source.replace(needle, 'let (name, name_len, _h) = field_name_hash(recs, &mut p); let h = 0u64;')
    forced_path = tmp/'constant.rs'
    forced_path.write_text(forced)
    run(sys.executable, HERE/'reference.py', '--source', forced_path, '--seeds', '8',
        *(['--avx2'] if args.avx2 else []))
    for tail, slots in (('cache-tail.rs', 32768), ('independent-tail.rs', 1), ('independent-tail.rs', 32768)):
        modified = source.replace('const CACHE_SLOTS: usize = 32768;', f'const CACHE_SLOTS: usize = {slots};')
        assert modified != source or slots == 32768
        src = tmp/f'{tail}-{slots}.rs'
        exe = tmp/f'{tail}-{slots}'
        src.write_text(modified + '\n' + (HERE/tail).read_text())
        run('rustc', '--edition=2021', '--crate-name', 'cache_test', '--test', '-O', '-C', 'overflow-checks=yes', *flags, src, '-o', exe)
        run(exe)
print('PASS rowcache rebased verification')
