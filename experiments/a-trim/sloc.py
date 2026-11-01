#!/usr/bin/env python3
"""Code lines (non-blank, not starting with //) of each file after `rustfmt --edition 2021`.

An approximation of the board's S (standard formatter, then a code-line count); the board's
own count may differ by a few lines.
"""
import shutil, subprocess, sys, tempfile
from pathlib import Path

for p in sys.argv[1:]:
    with tempfile.TemporaryDirectory() as t:
        f = Path(t) / "x.rs"
        shutil.copy(p, f)
        subprocess.run(["rustfmt", "--edition", "2021", str(f)], check=True)
        lines = [l.strip() for l in f.read_text().splitlines()]
    code = sum(1 for l in lines if l and not l.startswith("//"))
    print(f"{p}: code {code}, formatted total {len(lines)}")
