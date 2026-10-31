#!/usr/bin/env python3
"""Compare a directory-interface B binary with the reference on all tiny tokens."""
import itertools
import os
from pathlib import Path
import string
import subprocess
import sys
import tempfile

if len(sys.argv) != 2:
    raise SystemExit('usage: fixture.py /path/to/solution')
binary = str(Path(sys.argv[1]).resolve(strict=True))
repo = Path(__file__).resolve().parents[2]
alphabet = string.ascii_lowercase + string.digits
terms = [''.join(x) for n in (1, 2, 3) for x in itertools.product(alphabet, repeat=n)]
with tempfile.TemporaryDirectory(prefix='b-tiny-direct-') as tmp:
    root = Path(tmp)
    data, ref, out = (root / x for x in ('data', 'ref', 'out'))
    for directory in (data, ref, out):
        directory.mkdir()
    with (data / 'docs.txt').open('w') as f:
        for i in range(0, len(terms), 250):
            f.write(f'{i // 250}\t' + ' '.join(terms[i:i + 250]) + '\n')
    with (data / 'queries.txt').open('w') as f:
        for term in terms:
            f.write('BOOL ' + term + '\n')
        f.write('PHRASE "a aa"\nBOOL a OR aa NOT aaa\nBOOL 0 OR 00 AND 000\n')
    subprocess.run([sys.executable, str(repo / 'official/reference/b_index.py'),
                    '--data', str(data), '--out', str(ref)], check=True)
    env = dict(os.environ, SD_DATA=str(data), SD_OUT=str(out))
    subprocess.run([binary], env=env, check=True)
    if (ref / 'results.txt').read_bytes() != (out / 'results.txt').read_bytes():
        raise SystemExit('candidate differs from reference')
print(f'PASS {len(terms)} one-to-three-byte tokens against reference')
