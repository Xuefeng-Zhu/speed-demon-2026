#!/usr/bin/env python3
"""Exact-source WordBatch properties; optionally require real Linux AVX2."""
import argparse
import hashlib
import platform
import subprocess
import tempfile
from pathlib import Path

here = Path(__file__).resolve().parent
source = (here / 'candidate.rs').read_text()
tail = (here / 'property-tail.rs').read_text()
transitions = (here / 'token-tail.rs').read_text()
assert hashlib.sha256(source.encode()).hexdigest() == 'ebfb413f8dc95cf9071ab9d8dd8e0d3deb0d2f303fb924d68f3c0bf1caae4ad8'
parser = argparse.ArgumentParser()
parser.add_argument('--x86-v3', action='store_true')
args = parser.parse_args()

if args.x86_v3:
    if platform.system() != 'Linux' or platform.machine() not in ('x86_64', 'amd64'):
        raise SystemExit('--x86-v3 requires Linux x86-64')
    features = set(Path('/proc/cpuinfo').read_text().lower().split('flags', 1)[1].splitlines()[0].split())
    required = {'avx', 'avx2', 'bmi1', 'bmi2', 'f16c', 'fma', 'movbe', 'pni', 'popcnt',
                'sse4_1', 'sse4_2', 'ssse3', 'xsave', 'cx16', 'lahf_lm'}
    if not required <= features:
        raise SystemExit('x86-64-v3 preflight missing: ' + ', '.join(sorted(required - features)))
    if not ({'abm', 'lzcnt'} & features):
        raise SystemExit('x86-64-v3 preflight missing: lzcnt/abm')

print('candidate sha256:', hashlib.sha256(source.encode()).hexdigest())
marker = '''    fn short_hash(mut x: u64) -> usize {
        x ^= x >> 30;
        x = x.wrapping_mul(0xbf58_476d_1ce4_e5b9);
        x ^= x >> 27;
        x = x.wrapping_mul(0x94d0_49bb_1331_11eb);
        ((x ^ (x >> 31)) >> 32) as usize
    }'''
assert source.count(marker) == 1
forced = source.replace(marker, '    fn short_hash(_x: u64) -> usize { 0 }')
with tempfile.TemporaryDirectory(prefix='b-gather-property-') as tmp:
    for label, text in [('normal', source), ('forced-zero-hash', forced)]:
        path = Path(tmp) / (label + '.rs')
        binary = Path(tmp) / label
        # Full random coverage runs against the normal hash; use a smaller
        # deterministic sample with the intentionally quadratic zero hash.
        suite = tail if label == 'normal' else tail.replace('0..1500', '0..40')
        path.write_text(text + '\n' + suite + ('\n' + transitions if label == 'normal' else ''))
        cmd = ['rustc', '--edition=2021', '--test', '-O', '-C', 'overflow-checks=yes',
               '-C', 'debug-assertions=yes']
        if args.x86_v3:
            cmd += ['-C', 'target-cpu=x86-64-v3']
        subprocess.run([*cmd, str(path), '-o', str(binary)], check=True)
        result = subprocess.run([str(binary), '--test-threads=1'], text=True,
                                capture_output=True, check=True)
        print(label, result.stdout)
        if args.x86_v3 and 'target_gather_sanitizes_miss_at_guarded_tables ... ok' not in result.stdout:
            raise SystemExit('actual x86 gather guard test did not run')
