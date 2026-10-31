#!/usr/bin/env python3
"""Compare supplied executables with official reference on fresh generator seeds."""
import argparse
import os
from pathlib import Path
import subprocess
import sys
import tempfile

here = Path(__file__).resolve().parent
p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--binary', action='append', type=Path, required=True)
a = p.parse_args()
binaries = [x.resolve(strict=True) for x in a.binary]
count = 0
with tempfile.TemporaryDirectory(prefix='sd-a-pgo-check-') as tmp:
    root = Path(tmp)
    for seed in (2, 17, 99, 4242, 76543):
        case = root / str(seed)
        data, ref = case / 'data', case / 'reference'
        ref.mkdir(parents=True)
        subprocess.run([sys.executable, str(here.parent / 'context/generator.py'), '--seed', str(seed), '--scale', 'tiny', '--out', str(data)], check=True, stdout=subprocess.DEVNULL)
        subprocess.run([sys.executable, str(here / 'reference.py'), '--data', str(data), '--out', str(ref)], check=True, stdout=subprocess.DEVNULL)
        expected = (ref / 'summary.txt').read_bytes()
        for index, binary in enumerate(binaries):
            out = case / f'candidate-{index}'
            out.mkdir()
            for threads in (1, 2, 6, 12):
                subprocess.run([str(binary)], env={**os.environ, 'SD_DATA': str(data), 'SD_OUT': str(out), 'SD_THREADS': str(threads)}, check=True)
                assert (out / 'summary.txt').read_bytes() == expected, (seed, binary, threads)
                count += 1
print(f'PASS: {count} generated reference comparisons')
