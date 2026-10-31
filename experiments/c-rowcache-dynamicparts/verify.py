#!/usr/bin/env python3
"""Reference checks for dynamic owner partitions, including all-equal prehash."""
import argparse
from pathlib import Path
import subprocess
import sys
import tempfile
p = argparse.ArgumentParser()
p.add_argument('--avx2', action='store_true')
a = p.parse_args()
here = Path(__file__).resolve().parent
source = (here / 'parts4.rs').read_text()
needle = 'let (name, name_len, h) = field_name_hash(recs, &mut p);'
assert source.count(needle) == 1
extra = ['--avx2'] if a.avx2 else []
subprocess.run([sys.executable, str(here / 'reference.py'), '--source', str(here / 'parts4.rs'), '--seeds', '24', *extra], check=True)
with tempfile.TemporaryDirectory(prefix='c-dyn-owner-') as tmp:
    forced = Path(tmp) / 'forced.rs'
    forced.write_text(source.replace(needle, 'let (name, name_len, _h) = field_name_hash(recs, &mut p); let h = 0u64;'))
    subprocess.run([sys.executable, str(here / 'reference.py'), '--source', str(forced), '--seeds', '8', *extra], check=True)
