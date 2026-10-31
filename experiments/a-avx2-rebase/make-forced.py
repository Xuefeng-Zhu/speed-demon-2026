#!/usr/bin/env python3
"""Write a test-only source forcing every endpoint hash to zero."""
import argparse
from pathlib import Path
p = argparse.ArgumentParser()
p.add_argument('--source', required=True, type=Path)
p.add_argument('--output', required=True, type=Path)
a = p.parse_args()
s = a.source.read_text()
x = 'let (e, h) = unsafe { endpoint(d, s) };'
y = 'let (e, _) = unsafe { endpoint(d, s) }; let h = 0u64;'
assert s.count(x) == 1
s = s.replace(x, y)
a.output.write_text(s)
