#!/usr/bin/env python3
"""Reference, forced-collision, alignment and guard checks for short equality."""
import argparse
from pathlib import Path
import subprocess
import sys
import tempfile

here = Path(__file__).resolve().parent
p = argparse.ArgumentParser()
p.add_argument('--avx2', action='store_true', help='actual x86-64-v3 path; requires capable x86')
a = p.parse_args()
extra = ['--avx2'] if a.avx2 else []
def run(*args): subprocess.run([str(x) for x in args], check=True)
run(sys.executable, here/'run-tests.py', *extra)
run(sys.executable, here/'reference.py', '--source', here/'candidate.rs', '--seeds', '24', *extra)
source = (here/'candidate.rs').read_text()
needle = 'let (name, name_len, h) = field_name_hash(recs, &mut p);'
assert source.count(needle) == 1
forced = source.replace(needle, 'let (name, name_len, _h) = field_name_hash(recs, &mut p); let h = 0u64;')
with tempfile.TemporaryDirectory(prefix='sd-c-short-eq-verify-') as tmp:
    p = Path(tmp)/'forced.rs'
    p.write_text(forced)
    run(sys.executable, here/'reference.py', '--source', p, '--seeds', '8', *extra)
print('PASS short exact equality verification')
