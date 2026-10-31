#!/usr/bin/env python3
"""Compare C++ or Rust candidate tracks with the official references.

By default the candidate and official directories are taken from this script's
repository. --candidate-root permits testing a separate checkout, including a
mixture of C++ and Rust tracks; --official-root overrides the generator/reference
location independently. Rust binary names come from Cargo metadata rather than a
hard-coded package name. All Cargo operations are offline and use per-track build
directories.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parent.parent
FILES = {'a': ('a_ingest', 'summary.txt'), 'b': ('b_index', 'results.txt'),
         'c': ('c_join', 'aggregates.txt'), 'd': ('d_traverse', 'distances.txt')}


def build(track, source, temp):
    manifest = source / 'Cargo.toml'
    if manifest.is_file():
        target = temp / ('cargo-target-' + track)
        env = dict(os.environ, CARGO_TARGET_DIR=str(target))
        metadata = json.loads(subprocess.check_output(
            ['cargo', 'metadata', '--offline', '--no-deps', '--format-version', '1',
             '--manifest-path', str(manifest)], cwd=source, env=env, text=True))
        packages = [p for p in metadata['packages'] if Path(p['manifest_path']).resolve() == manifest.resolve()]
        if len(packages) != 1:
            raise RuntimeError(f'{manifest}: expected exactly one package')
        bins = [t['name'] for t in packages[0]['targets'] if 'bin' in t['kind']]
        if len(bins) != 1:
            raise RuntimeError(f'{manifest}: expected exactly one binary target, found {bins}')
        subprocess.run(['cargo', 'build', '--release', '--offline', '--manifest-path', str(manifest),
                        '--bin', bins[0]], cwd=source, env=env, check=True)
        return target / 'release' / bins[0], 'directories'
    cpp = source / 'main.cpp'
    if not cpp.is_file():
        raise RuntimeError(f'{source}: expected Cargo.toml or main.cpp')
    exe = temp / ('candidate-' + track)
    subprocess.run(['c++', '-std=c++17', '-O3', '-DNDEBUG', '-pthread', str(cpp), '-o', str(exe)], check=True)
    return exe, 'paths'


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--tracks', default='abcd')
    p.add_argument('--seeds', nargs='+', type=int, default=[2, 17, 4242])
    p.add_argument('--scale', choices=('tiny', 'sample'), default='tiny')
    p.add_argument('--report')
    p.add_argument('--candidate-root', type=Path, default=ROOT, help='checkout containing track-a through track-d')
    p.add_argument('--official-root', type=Path, default=ROOT / 'official', help='directory containing generators and reference')
    a = p.parse_args()
    if not a.tracks or any(t not in FILES for t in a.tracks) or len(set(a.tracks)) != len(a.tracks):
        p.error('tracks must be distinct letters from abcd')
    candidates, official = a.candidate_root.resolve(), a.official_root.resolve()
    report = []
    with tempfile.TemporaryDirectory(prefix='speed-demon-diff-') as temp:
        tmp = Path(temp)
        binaries = {t: build(t, candidates / ('track-' + t), tmp) for t in a.tracks}
        for t in a.tracks:
            module, output = FILES[t]
            exe, io = binaries[t]
            for seed in a.seeds:
                work = tmp / f'{t}-{seed}'
                data, ref, actual = (work / x for x in ('data', 'reference', 'candidate'))
                ref.mkdir(parents=True)
                actual.mkdir()
                subprocess.run([sys.executable, str(official / 'generators' / (module + '.py')),
                                '--seed', str(seed), '--scale', a.scale, '--out', str(data)],
                               check=True, stdout=subprocess.DEVNULL)
                subprocess.run([sys.executable, str(official / 'reference' / (module + '.py')),
                                '--data', str(data), '--out', str(ref)], check=True)
                if io == 'directories' or t == 'd':
                    cmd = [str(exe)]
                elif t == 'a':
                    cmd = [str(exe), str(data / 'requests.log'), str(actual / output)]
                elif t == 'b':
                    cmd = [str(exe), str(data / 'docs.txt'), str(data / 'queries.txt'), str(actual / output)]
                else:
                    cmd = [str(exe), str(data), str(actual)]
                # Rust PR tracks use SD_*, while the current Rust D uses DATA_DIR/OUT_DIR.
                env = dict(os.environ, DATA_DIR=str(data), OUT_DIR=str(actual), SD_DATA=str(data), SD_OUT=str(actual))
                subprocess.run(cmd, env=env, check=True)
                found = sorted(p.name for p in actual.iterdir())
                if found != [output]:
                    raise SystemExit(f'FAIL track {t} seed {seed}: output files {found}, expected {[output]}')
                refbytes, actualbytes = (ref / output).read_bytes(), (actual / output).read_bytes()
                if refbytes != actualbytes:
                    raise SystemExit(f'FAIL track {t} seed {seed}: output differs from reference')
                row = {'track': t, 'seed': seed, 'scale': a.scale, 'sha256': hashlib.sha256(refbytes).hexdigest()}
                report.append(row)
                print('PASS', json.dumps(row), flush=True)
    if a.report:
        Path(a.report).write_text(json.dumps(report, indent=2) + '\n')


if __name__ == '__main__':
    main()
