#!/usr/bin/env python3
"""Check one exact expected latency for each of 72 * 1842 distinct groups."""
import argparse
import datetime
import os
from pathlib import Path
import random
import subprocess
import tempfile

ap=argparse.ArgumentParser(); ap.add_argument('--binary',required=True); args=ap.parse_args()
binary=str(Path(args.binary).resolve())
rng=random.Random(20261031)
with tempfile.TemporaryDirectory(prefix='speed-a-latency-grid-') as td:
    d=Path(td); records=[]; expected=[]
    start=datetime.datetime(2026,10,30,18)
    for hour in range(72):
        when=start+datetime.timedelta(hours=hour)
        ts=when.strftime('%Y-%m-%dT%H:%M:%S.000000Z')
        group=when.strftime('%Y-%m-%dT%H:00:00Z')
        for idx in range(1842):
            endpoint=f'/grid/{idx:04}'
            width=(hour+idx)%10+1
            lo=0 if width==1 else 10**(width-1)
            hi=min(4294967295,10**width-1)
            latency=rng.randint(lo,hi)
            if idx==0: latency=0
            if idx==1: latency=4294967295
            status=599 if idx%2 else 499
            error=int(status==599)
            records.append(f'{ts} GET {endpoint} {status} {latency}\n')
            expected.append(f'{group} {endpoint} 1 {latency} {latency} {latency} {error} {error*1000000}\n')
    rng.shuffle(records)
    (d/'requests.log').write_text(''.join(records),encoding='ascii')
    want=''.join(expected).encode('ascii')
    for threads in (1,2,6,12,64):
        subprocess.run([binary],env={**os.environ,'SD_DATA':str(d),'SD_OUT':str(d),'SD_THREADS':str(threads)},check=True)
        got=(d/'summary.txt').read_bytes()
        assert got==want, f'output differs with {threads} threads'
        print(f'PASS {len(records)} groups, {threads} threads',flush=True)
