#!/usr/bin/env python3
"""Compare a candidate to the official Track B reference on edge cases."""
import argparse
import subprocess
import sys
import tempfile
from pathlib import Path

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('candidate', help='path to compiled Track B candidate')
parser.add_argument('reference', help='path to official reference/b_index.py')
args = parser.parse_args()
with tempfile.TemporaryDirectory(prefix='b-edges-') as tmp:
    root = Path(tmp)
    data, ref, out = (root / d for d in ('data', 'reference', 'out'))
    for p in (data, ref, out): p.mkdir()
    long = 'x' * 32
    texts = ['', f'{long}  {long} And AND and', f'X{long[1:]} — 007 7 zürich', '§§ ¶',
             'a b a b a b', 'and OR not', 'in.the!matter/of']
    (data / 'docs.txt').write_text(''.join(f'{i}\t{t}\n' for i, t in enumerate(texts)), encoding='utf-8')
    queries = [f'BOOL {long}', f'PHRASE "{long} {long}"', 'BOOL and AND not',
               'BOOL a OR and NOT b', 'PHRASE "a b a"', 'BOOL 007 OR 7',
               'PHRASE "in the matter of"', 'BOOL zurich', 'BOOL z AND rich', 'PHRASE "not and"']
    (data / 'queries.txt').write_text('\n'.join(queries * 100) + '\n', encoding='ascii')
    subprocess.run([sys.executable, args.reference, '--data', str(data), '--out', str(ref)], check=True)
    subprocess.run([args.candidate, str(data / 'docs.txt'), str(data / 'queries.txt'), str(out / 'results.txt')], check=True)
    assert (ref / 'results.txt').read_bytes() == (out / 'results.txt').read_bytes()
    print('PASS 1,000 edge and repeated queries')
