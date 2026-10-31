#!/usr/bin/env python3
"""Generate independent seeds and compare all candidate outputs to official references."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

root = Path(__file__).resolve().parent.parent
p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--tracks', default='abcd')
p.add_argument('--seeds', nargs='+', type=int, default=[2, 17, 4242])
p.add_argument('--scale', choices=('tiny', 'sample'), default='tiny')
p.add_argument('--report')
a = p.parse_args()
if not a.tracks or any(t not in 'abcd' for t in a.tracks) or len(set(a.tracks)) != len(a.tracks):
    p.error('tracks must be distinct letters from abcd')
files = {'a': ('a_ingest', 'summary.txt'), 'b': ('b_index', 'results.txt'),
         'c': ('c_join', 'aggregates.txt'), 'd': ('d_traverse', 'distances.txt')}
report = []
with tempfile.TemporaryDirectory(prefix='speed-demon-diff-') as temp:
    tmp = Path(temp)
    binaries = {}
    for t in a.tracks:
        src = root / ('track-' + t)
        exe = tmp / ('candidate-' + t)
        if t == 'd':
            env = dict(os.environ, CARGO_TARGET_DIR=str(tmp / 'cargo-target'))
            subprocess.run(['cargo', 'build', '--release', '--offline', '--manifest-path', str(src / 'Cargo.toml')], env=env, check=True)
            exe = tmp / 'cargo-target' / 'release' / 'traverse'
        else:
            subprocess.run(['c++', '-std=c++17', '-O3', '-DNDEBUG', '-pthread', str(src / 'main.cpp'), '-o', str(exe)], check=True)
        binaries[t] = exe
    for t in a.tracks:
        module, output = files[t]
        for seed in a.seeds:
            work = tmp / f'{t}-{seed}'
            data, ref, actual = (work / x for x in ('data', 'reference', 'candidate'))
            ref.mkdir(parents=True)
            actual.mkdir()
            subprocess.run([sys.executable, str(root / 'official' / 'generators' / (module + '.py')), '--seed', str(seed), '--scale', a.scale, '--out', str(data)], check=True, stdout=subprocess.DEVNULL)
            subprocess.run([sys.executable, str(root / 'official' / 'reference' / (module + '.py')), '--data', str(data), '--out', str(ref)], check=True)
            if t == 'a':
                cmd = [str(binaries[t]), str(data / 'requests.log'), str(actual / output)]
            elif t == 'b':
                cmd = [str(binaries[t]), str(data / 'docs.txt'), str(data / 'queries.txt'), str(actual / output)]
            elif t == 'c':
                cmd = [str(binaries[t]), str(data), str(actual)]
            else:
                cmd = [str(binaries[t])]
            env = dict(os.environ, DATA_DIR=str(data), OUT_DIR=str(actual))
            subprocess.run(cmd, env=env, check=True)
            refbytes, actualbytes = (ref / output).read_bytes(), (actual / output).read_bytes()
            if refbytes != actualbytes:
                raise SystemExit(f'FAIL track {t} seed {seed}: output differs from reference')
            row = {'track': t, 'seed': seed, 'scale': a.scale, 'sha256': hashlib.sha256(refbytes).hexdigest()}
            report.append(row)
            print('PASS', json.dumps(row), flush=True)
if a.report:
    Path(a.report).write_text(json.dumps(report, indent=2) + '\n')
