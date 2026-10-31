#!/usr/bin/env python3
"""Compare Rust C to the official reference across CSV boundaries and worker counts."""
import argparse
import os
from pathlib import Path
import random
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parent.parent


def quote(value):
    return '"' + value.replace('"', '""') + '"'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=ROOT / 'track-c/src/main.rs')
    parser.add_argument('--reference', type=Path, default=ROOT / 'official/reference/c_join.py')
    parser.add_argument('--seeds', type=int, default=24, help='number of deterministic cases')
    args = parser.parse_args()
    if args.seeds < 1:
        parser.error('--seeds must be positive')
    source = args.source.resolve().read_text()
    reference = args.reference.resolve()
    needle = 'let n = thread::available_parallelism().map_or(1, |n| n.get());'
    if source.count(needle) != 1:
        parser.error('source does not have the expected worker-count statement')

    with tempfile.TemporaryDirectory(prefix='speed-c-independent-') as temp:
        root = Path(temp)
        workers = (1, 2, 3, 7, 16)
        for n in workers:
            src = root / f'c{n}.rs'
            src.write_text(source.replace(needle, f'let n = {n};'))
            subprocess.run(['rustc', '-O', '--edition', '2021', str(src),
                            '-o', str(root / f'c{n}')], check=True)
        for seed in range(args.seeds):
            rng = random.Random(seed)
            with tempfile.TemporaryDirectory(prefix='case-', dir=root) as case:
                case = Path(case)
                data, ref = case / 'data', case / 'ref'
                data.mkdir()
                ref.mkdir()
                (data / 'regions.csv').write_bytes(b'region_id,country\n1,AAA\n2,BBB\n9,AAA\n')
                chunks = [b'\xef\xbb\xbfid,name,note,region_id,amount\r\n']
                for i in range(1, 150):
                    name = rng.choice(['', 'Alice', 'A quote " here', 'B, C',
                                       'n' * rng.choice([1, 64, 997, 4095]), 'N  '])
                    note = rng.choice(['', '"', 'alpha\nbeta', '"begin\nend"', 'x, y',
                                       'z' * rng.choice([1, 20, 1009])])
                    name_field = quote(name) if name or rng.randrange(2) else ''
                    note_field = quote(note) if note or rng.randrange(2) else ''
                    amount = rng.choice(['0.00', '-0.05', '-999.99', '99999.99', '1.25'])
                    region = rng.choice([1, 2, 9, 5000000])
                    line = f'{i},{name_field},{note_field},{region},{amount}'
                    bom = b'\xef\xbb\xbf' if i > 1 and rng.randrange(9) == 0 else b''
                    chunks.append(bom + line.encode() + rng.choice([b'\n', b'\r\n']))
                (data / 'records.csv').write_bytes(b''.join(chunks))
                subprocess.run(['python3', str(reference), '--data', str(data), '--out', str(ref)],
                               check=True, stdout=subprocess.DEVNULL)
                expected = (ref / 'aggregates.txt').read_bytes()
                for n in workers:
                    out = case / f'out{n}'
                    out.mkdir()
                    env = dict(os.environ, SD_DATA=str(data), SD_OUT=str(out))
                    subprocess.run([str(root / f'c{n}')], env=env, check=True)
                    actual = (out / 'aggregates.txt').read_bytes()
                    if actual != expected:
                        raise SystemExit(f'FAIL seed={seed} workers={n}')
    print(f'PASS: {args.seeds} corpora x {len(workers)} worker counts against reference')


if __name__ == '__main__':
    main()
