#!/usr/bin/env python3
"""Compare an A binary on alternating empty, small and large hourly groups."""
import argparse
from datetime import datetime, timedelta
import os
from pathlib import Path
import subprocess
import sys
import tempfile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--binary', type=Path, required=True)
    parser.add_argument('--reference', type=Path, required=True)
    args = parser.parse_args()
    binary, reference = args.binary.resolve(), args.reference.resolve()
    with tempfile.TemporaryDirectory(prefix='a-reuse-state-') as tmp:
        root = Path(tmp)
        data, ref = root / 'data', root / 'ref'
        data.mkdir()
        ref.mkdir()
        start = datetime(2026, 10, 30, 18)
        with (data / 'requests.log').open('w') as f:
            for h in range(72):
                count = (0, 1, 83, 700, 2, 1900, 3, 0)[h % 8]
                groups = (1, 1, 47, 300, 2, 1100, 3, 1)[h % 8]
                for i in range(count):
                    stamp = (start + timedelta(hours=h, seconds=i % 3600)).strftime(
                        '%Y-%m-%dT%H:%M:%S.000000Z')
                    endpoint = '/m' + str((i * 97 + h) % groups)
                    status = (200, 500, 599)[(i + h) % 3]
                    latency = (0, 4294967295, (i * 1237 + h) % 100000)[(i + h) % 3]
                    f.write(f'{stamp} GET {endpoint} {status} {latency}\n')
        subprocess.run([sys.executable, str(reference), '--data', str(data),
                        '--out', str(ref)], check=True)
        expected = (ref / 'summary.txt').read_bytes()
        for workers in (1, 2, 3, 7, 12, 64):
            out = root / f'out-{workers}'
            out.mkdir()
            env = dict(os.environ, SD_DATA=str(data), SD_OUT=str(out),
                       SD_THREADS=str(workers))
            subprocess.run([str(binary)], env=env, check=True)
            if (out / 'summary.txt').read_bytes() != expected:
                raise SystemExit(f'FAIL workers={workers}')
        print('PASS 72 alternating empty/small/large hours; workers 1,2,3,7,12,64')


if __name__ == '__main__':
    main()
