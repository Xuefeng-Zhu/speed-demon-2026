#!/usr/bin/env python3
"""Check exact capacity source against references and replacement/collision model."""
import argparse
from pathlib import Path
import subprocess
import sys
import tempfile

parser = argparse.ArgumentParser()
parser.add_argument('--capacity', type=int, choices=[4096, 8192, 16384, 65536], required=True)
parser.add_argument('--avx2', action='store_true')
args = parser.parse_args()
here = Path(__file__).resolve().parent
source = here / f'cache-{args.capacity}.rs'
text = source.read_text()
assert text.count(f'const CACHE_SLOTS: usize = {args.capacity};') == 1
needle = 'let (name, name_len, h) = field_name_hash(recs, &mut p);'
assert text.count(needle) == 1
extra = ['--avx2'] if args.avx2 else []
subprocess.run([sys.executable, str(here / 'reference.py'), '--source', str(source), '--seeds', '24', *extra], check=True)
with tempfile.TemporaryDirectory(prefix='c-dyn-cache-capacity-') as temp:
    temp = Path(temp)
    forced = temp / 'forced.rs'
    forced.write_text(text.replace(needle, 'let (name, name_len, _h) = field_name_hash(recs, &mut p); let h = 0u64;'))
    subprocess.run([sys.executable, str(here / 'reference.py'), '--source', str(forced), '--seeds', '8', *extra], check=True)
    tests = temp / 'test.rs'
    tests.write_bytes(source.read_bytes() + b'\n' + (here / 'test-tail.rs').read_bytes())
    binary = temp / 'test'
    subprocess.run(['rustc', '--edition=2021', '--test', '-O', '-C', 'overflow-checks=yes', '-C', 'debug-assertions=yes', str(tests), '-o', str(binary)], check=True)
    subprocess.run([str(binary)], check=True)
