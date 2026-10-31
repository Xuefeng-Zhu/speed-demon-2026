#!/usr/bin/env python3
"""Compare exact baseline and candidate C parser functions on exhaustive inputs."""
import argparse
from pathlib import Path
import subprocess
import tempfile

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--baseline', type=Path, required=True)
p.add_argument('--candidate', type=Path, required=True)
a = p.parse_args()

def grab(s, name, end):
    start = s.index('fn ' + name + '(')
    return s[start:s.index(end, start)]

orig = a.baseline.read_text()
new = a.candidate.read_text()
body = 'extern "C" { fn memchr(s: *const u8, c: i32, n: usize) -> *const u8; }\n'
for prefix, text in [('old', orig), ('new', new)]:
    body += grab(text, 'field', '\n/// Parses `-?').replace('fn field(', 'fn ' + prefix + '_field(', 1) + '\n'
for prefix, text in [('old', orig), ('new', new)]:
    body += grab(text, 'number', '\n/// Section 2.2').replace('fn number(', 'fn ' + prefix + '_number(', 1) + '\n'
body += Path(__file__).with_name('property-main.rs').read_text()
with tempfile.TemporaryDirectory(prefix='c-fused-properties-') as td:
    src, exe = Path(td) / 'properties.rs', Path(td) / 'properties'
    src.write_text(body)
    subprocess.run(['rustc', '--edition=2021', '-O', '-C', 'overflow-checks=yes', str(src), '-o', str(exe)], check=True)
    subprocess.run([str(exe)], check=True)
