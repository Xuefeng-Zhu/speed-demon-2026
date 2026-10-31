#!/usr/bin/env python3
"""Compile two variants and measure interleaved, hash-checked native runs.

This is an iteration aid, not the official Docker/cgroup scoring harness.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import statistics
import subprocess
import tempfile
import time

ROOT = Path(__file__).resolve().parent.parent
HASHES = {
    'a': '495ca09682b9673ef836a506496177680bb4a3af54255174befddb1f83481cd3',
    'b': 'f86973c210228141bcb6f1f1b10188ad2a9b65f71e7cd7cf4590b38de4e80927',
    'c': 'd8088b1cd42ba1338b1345b107b55db7b96ef1f5066f3ff64fd26a8912a0f536',
    'd': 'a23dbdf0a3e49cc8901310a9ee1dc6a9a569a85297b6da75c2a7002cb2ed277e',
}
VARIANTS = {
    'a': {'three-shard-insert': 'experiments/a-three-shard-insert.cpp', 'serial-f45': 'experiments/a-serial-f45.cpp', 'three-shard-checked': 'experiments/a-three-shard-checked.cpp', 'striped': 'experiments/a-striped.cpp', 'buffered': 'experiments/a-output-buffered.cpp', 'parallel': 'experiments/a-parallel-output.cpp'},
    'b': {'stream-2fc': 'experiments/b-stream-2fc.cpp', 'serial': 'experiments/b-serial.cpp', 'parallel': 'experiments/b-parallel-query.cpp', 'parallel-index': 'experiments/b-parallel-index.cpp', 'stream-index': 'experiments/b-stream-index.cpp', 'zero-copy': 'experiments/b-zero-copy.cpp'},
    'c': {'mmap-2fc': 'experiments/c-mmap-2fc.cpp', 'heap-664': 'experiments/c-heap-664.cpp', 'mmap': 'experiments/c-mmap.cpp', 'workers-3': 'experiments/c-workers-3.cpp', 'workers-12': 'experiments/c-workers-12.cpp', 'serial': 'experiments/c-serial.cpp', 'hash-sort': 'experiments/c-hashsort.cpp'},
    'd': {'parallel-parse': 'experiments/track-d-parallel-parse/Cargo.toml', 'dense': 'experiments/track-d-dense/Cargo.toml', 'sparse': 'experiments/track-d-sparse/Cargo.toml', 'seen16': 'experiments/track-d-seen16/Cargo.toml', 'packed': 'experiments/track-d-packed/Cargo.toml', 'packed-u32': 'experiments/track-d-packed-u32/Cargo.toml'},
}
OUTPUT = {'a': 'summary.txt', 'b': 'results.txt', 'c': 'aggregates.txt', 'd': 'distances.txt'}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('track', choices=VARIANTS)
    ap.add_argument('variant', help='variant name for this track')
    ap.add_argument('--baseline-variant', help='compare against a named variant instead of the selected candidate')
    ap.add_argument('--data', type=Path, required=True, help='generated input directory')
    ap.add_argument('--expected', help='output hash; defaults to published seed-1 full hash')
    ap.add_argument('--runs', type=int, default=5)
    ap.add_argument('--warmups', type=int, default=1)
    ap.add_argument('--report', type=Path, help='write results as JSON')
    args = ap.parse_args()
    if args.variant not in VARIANTS[args.track]:
        ap.error(f"variants for {args.track}: {', '.join(VARIANTS[args.track])}")
    if args.baseline_variant and args.baseline_variant not in VARIANTS[args.track]:
        ap.error('unknown baseline variant for this track')
    if args.runs < 1 or args.warmups < 0 or not args.data.is_dir():
        ap.error('data must exist; runs must be positive and warmups nonnegative')
    data = args.data.resolve()
    expected = (args.expected or HASHES[args.track]).lower()
    if len(expected) != 64 or any(c not in '0123456789abcdef' for c in expected):
        ap.error('expected must be a SHA-256 hex digest')
    track = args.track
    with tempfile.TemporaryDirectory(prefix='speed-demon-compare-') as td:
        tmp = Path(td)
        base = ROOT / VARIANTS[track][args.baseline_variant] if args.baseline_variant else ROOT / ('track-' + track)
        sources = {'baseline': base, 'variant': ROOT / VARIANTS[track][args.variant]}
        binaries = {}
        source_hashes = {}
        for label, src in sources.items():
            if track == 'd':
                manifest = src / 'Cargo.toml' if src.is_dir() else src
                source_file = manifest.parent / 'src/main.rs'
                source_hashes[label] = hashlib.sha256(source_file.read_bytes()).hexdigest()
                target = tmp / ('target-' + label)
                env = dict(os.environ, CARGO_TARGET_DIR=str(target))
                subprocess.run(['cargo', 'build', '--release', '--offline', '--manifest-path', str(manifest)], env=env, check=True)
                binaries[label] = target / 'release' / 'traverse'
            else:
                file = src / 'main.cpp' if src.is_dir() else src
                source_hashes[label] = hashlib.sha256(file.read_bytes()).hexdigest()
                binaries[label] = tmp / label
                subprocess.run(['c++', '-std=c++17', '-O3', '-DNDEBUG', '-pthread', str(file), '-o', str(binaries[label])], check=True)
        outdir = tmp / 'out'
        outdir.mkdir()
        output = outdir / OUTPUT[track]
        report = {'track': track, 'variant': args.variant, 'platform': platform.platform(),
                  'baseline': args.baseline_variant or 'selected', 'data': str(data), 'expected_sha256': expected, 'runs': args.runs,
                  'warmups': args.warmups,
                  'source_sha256': source_hashes,
                  'compiler': subprocess.check_output(['rustc' if track == 'd' else 'c++', '--version'], text=True).splitlines()[0],
                  'measurements': {'baseline': [], 'variant': []},
                  'rss_note': 'Per-process maximum RSS; Linux reports KiB, macOS reports bytes. Not cgroup memory.',
                  'wall_note': 'Wall time includes process startup; this is not the official harness.'}
        for i in range(-args.warmups, args.runs):
            order = ('baseline', 'variant') if i % 2 == 0 else ('variant', 'baseline')
            for label in order:
                output.unlink(missing_ok=True)
                binary = str(binaries[label])
                env = os.environ.copy()
                if track == 'a':
                    cmd = [binary, str(data / 'requests.log'), str(output)]
                elif track == 'b':
                    cmd = [binary, str(data / 'docs.txt'), str(data / 'queries.txt'), str(output)]
                elif track == 'c':
                    cmd = [binary, str(data), str(outdir)]
                else:
                    cmd = [binary]
                    env.update(DATA_DIR=str(data), OUT_DIR=str(outdir))
                started = time.perf_counter()
                proc = subprocess.Popen(cmd, env=env, stdout=subprocess.DEVNULL)
                _, status, usage = os.wait4(proc.pid, 0)
                elapsed = time.perf_counter() - started
                proc.returncode = os.waitstatus_to_exitcode(status)
                if proc.returncode != 0:
                    raise SystemExit(f'{label}: exit {proc.returncode}')
                with output.open('rb') as f:
                    digest = hashlib.file_digest(f, 'sha256').hexdigest()
                if digest != expected:
                    raise SystemExit(f'{label}: wrong output hash {digest}')
                sample = {'wall_s': elapsed, 'user_s': usage.ru_utime, 'system_s': usage.ru_stime,
                          'max_rss_native_units': usage.ru_maxrss}
                if i >= 0:
                    report['measurements'][label].append(sample)
                    print(label, i + 1, sample, flush=True)
        for label, samples in report['measurements'].items():
            report[label + '_median_wall_s'] = statistics.median(x['wall_s'] for x in samples)
            report[label + '_max_rss_native_units'] = max(x['max_rss_native_units'] for x in samples)
        report['baseline_over_variant_median_time'] = report['baseline_median_wall_s'] / report['variant_median_wall_s']
        rendered = json.dumps(report, indent=2) + '\n'
        print(rendered, end='')
        if args.report:
            args.report.write_text(rendered)


if __name__ == '__main__':
    main()
