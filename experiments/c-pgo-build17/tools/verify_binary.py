#!/usr/bin/env python3
"""Compare actual supplied executables to the official reference on fresh data."""
import argparse
import os
from pathlib import Path
import subprocess
import sys
import tempfile

HERE = Path(__file__).resolve().parent
GENERATOR = HERE.parent / 'context' / 'generator.py'
REFERENCE = HERE / 'reference.py'

def call(args, **kwargs):
    subprocess.run(args, check=True, stdout=subprocess.DEVNULL, **kwargs)

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--binary', action='append', required=True, type=Path)
    args = parser.parse_args()
    bins = [p.resolve(strict=True) for p in args.binary]
    checks = 0
    with tempfile.TemporaryDirectory(prefix='sd-c-pgo-check-') as tmp:
        root = Path(tmp)
        for seed in (2, 17, 99, 4242, 76543, 'hostile'):
            case = root / str(seed)
            data, ref = case / 'data', case / 'reference'
            ref.mkdir(parents=True)
            if seed == 'hostile':
                data.mkdir()
                (data / 'regions.csv').write_bytes(b'region_id,country\n1,AAA\n2,BBB\n')
                (data / 'records.csv').write_bytes(
                    b'\xef\xbb\xbfid,name,note,region_id,amount\r\n'
                    b'1,"a,""b""","alpha\nbeta",1,-0.05\n'
                    b'\xef\xbb\xbf2,,"",2,1.25\r\n'
                    + b'3,"' + b'x' * 70000 + b'","comma, quote """,1,9.00\n'
                    + b'4,"' + b'x' * 70000 + b'","",1,-1.00\r\n')
            else:
                call([sys.executable, str(GENERATOR), '--seed', str(seed), '--scale', 'tiny', '--out', str(data)])
            call([sys.executable, str(REFERENCE), '--data', str(data), '--out', str(ref)])
            expected = (ref / 'aggregates.txt').read_bytes()
            for i, binary in enumerate(bins):
                out = case / f'candidate-{i}'
                out.mkdir()
                env = dict(os.environ, SD_DATA=str(data), SD_OUT=str(out))
                call([str(binary)], env=env)
                if (out / 'aggregates.txt').read_bytes() != expected:
                    raise RuntimeError(f'output mismatch: seed {seed}, binary {binary}')
                checks += 1
    print(f'PASS: {checks} generated and hostile reference comparisons of actual supplied binaries')

if __name__ == '__main__':
    main()
