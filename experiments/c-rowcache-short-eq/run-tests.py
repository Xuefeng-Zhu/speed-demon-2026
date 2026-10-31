#!/usr/bin/env python3
from pathlib import Path
import argparse, subprocess, tempfile
parser = argparse.ArgumentParser()
parser.add_argument("--avx2", action="store_true")
args = parser.parse_args()
flags = ["-C", "target-cpu=x86-64-v3"] if args.avx2 else []
p = Path(__file__).resolve().parent
with tempfile.TemporaryDirectory(prefix='sd-c-short-eq-') as t:
    t = Path(t)
    source = t / 'combined.rs'
    source.write_text((p / 'candidate.rs').read_text() + (p / 'test-tail.rs').read_text())
    binary = t / 'tests'
    subprocess.run(['rustc','--edition=2021','--test','-O','-C','overflow-checks=yes','-C','debug-assertions=yes',*flags,str(source),'-o',str(binary)],check=True)
    subprocess.run([str(binary),'--test-threads=1'],check=True)
