#!/usr/bin/env python3
"""Check exact per-group local-bitset union versus official C reference."""
import argparse
import hashlib
import os
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
EXPECTED = 'fb4d7ca03e49571aa7a6d03db26d67c3cd387458bdf86a453d2604dfbd066248'
p = argparse.ArgumentParser()
p.add_argument('--avx2', action='store_true')
a = p.parse_args()
s = (HERE / 'candidate.rs').read_text()
assert hashlib.sha256(s.encode()).hexdigest() == EXPECTED
needle = 'let n = thread::available_parallelism().map_or(1, |n| n.get());'
assert s.count(needle) == 1
flags = ['-C', 'target-cpu=x86-64-v3'] if a.avx2 else []

def code(i):
    return ''.join(chr(65 + (i // k) % 26) for k in (676, 26, 1))

def quote(v):
    return '"' + v.replace('"', '""') + '"'

with tempfile.TemporaryDirectory(prefix='c-local-groups-') as td:
    root = Path(td)
    for n in (1, 2, 3, 7, 12):
        src = root / f'c{n}.rs'
        src.write_text(s.replace(needle, f'let n = {n};'))
        subprocess.run(['rustc', '--edition=2021', '-O', '-C', 'overflow-checks=yes',
                        '-C', 'debug-assertions=yes', *flags, str(src), '-o', str(root / f'c{n}')], check=True)
    for groups in (1, 63, 64, 65, 240, 241, 256, 257, 17576):
        case = root / f'g{groups}'
        data, ref = case / 'data', case / 'ref'
        data.mkdir(parents=True)
        ref.mkdir()
        (data / 'regions.csv').write_text('region_id,country\n' + ''.join(f'{i+1},{code(i)}\n' for i in range(groups)))
        rows = [b'\xef\xbb\xbfid,name,note,region_id,amount\r\n']
        for i in range(1, max(1024, groups * 2) + 1):
            name = 'Name ' + chr(65 + (i % 101) // 26) + chr(65 + i % 26)
            if i % 19 == 0: name += ', "quoted"'
            if i % 23 == 0: name += ' '
            if i in (67, 68, 69): name = 'Long' + 'z' * (65534 + (i - 67))
            if i in (70, 71): name = ''
            field = '' if i == 70 else quote(name)
            note = quote('alpha\nbeta, "quote"')
            bom = b'\xef\xbb\xbf' if i % 137 == 0 else b''
            term = b'\r\n' if i % 7 == 0 or i == max(1024, groups * 2) else b'\n'
            rows.append(bom + f'{i},{field},{note},{1+(i % groups)},-0.05'.encode() + term)
        (data / 'records.csv').write_bytes(b''.join(rows))
        subprocess.run([sys.executable, str(ROOT / 'official/reference/c_join.py'), '--data', str(data), '--out', str(ref)], check=True, stdout=subprocess.DEVNULL)
        expected = (ref / 'aggregates.txt').read_bytes()
        for n in (1, 2, 3, 7, 12):
            out = case / f'o{n}'
            out.mkdir()
            subprocess.run([str(root / f'c{n}')], env=dict(os.environ, SD_DATA=str(data), SD_OUT=str(out)), check=True)
            assert (out / 'aggregates.txt').read_bytes() == expected, (groups, n)
print('PASS 9 group boundaries x 5 workers, duplicates, escaped/empty and long names')
