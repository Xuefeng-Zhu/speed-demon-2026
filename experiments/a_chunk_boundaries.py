#!/usr/bin/env python3
"""Exercise fixed 1 MiB read boundaries at several points in a maximum-length log line."""
import argparse
from pathlib import Path
import subprocess
import tempfile

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('binary', help='compiled Track A executable')
a = p.parse_args()
chunk = 1 << 20
prefix = '2026-10-30T18:00:00.000000Z '
base = prefix + 'GET / 200 1\n'
plus4 = prefix + 'OPTIONS / 200 1\n'
plus1 = prefix + 'HEAD / 200 1\n'
endpoint = '/' + 'x' * 124
target = prefix + 'OPTIONS ' + endpoint + ' 599 4294967295\n'
# Offsets put the split in the timestamp, method, endpoint, status and latency.
offsets = [1, 13, 27, 31, 45, 80, 160, len(target) - 3, len(target) - 1]
with tempfile.TemporaryDirectory(prefix='speed-a-boundaries-') as temp:
    data, output = Path(temp) / 'requests.log', Path(temp) / 'summary.txt'
    for offset in offsets:
        n, extra = divmod(chunk - offset, len(base))
        fours, ones = divmod(extra, 4)
        filler = plus4 * fours + plus1 * ones + base * (n - fours - ones)
        assert len(filler) == chunk - offset
        data.write_text(filler + target, encoding='ascii')
        subprocess.run([a.binary, str(data), str(output)], check=True)
        expected = f'2026-10-30T18:00:00Z / {n} 1 1 1 0 0\n2026-10-30T18:00:00Z {endpoint} 1 4294967295 4294967295 4294967295 1 1000000\n'
        assert output.read_text(encoding='ascii') == expected, f'bad split at {offset}'
        print('PASS boundary after target byte', offset, flush=True)
