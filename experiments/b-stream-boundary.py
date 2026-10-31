#!/usr/bin/env python3
"""Run the legacy >1 MiB boundary fixture against selected Rust Track B."""
import argparse
import os
from pathlib import Path
import subprocess
import sys
import tempfile

root = Path(__file__).resolve().parent.parent
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--binary', type=Path, help='use an existing compiled Rust executable')
args = parser.parse_args()

with tempfile.TemporaryDirectory(prefix='b-stream-boundary-') as td:
    temp = Path(td)
    if args.binary:
        binary = args.binary.resolve(strict=True)
    else:
        target = temp / 'target'
        env = dict(os.environ, CARGO_TARGET_DIR=str(target))
        subprocess.run(['cargo', 'build', '--release', '--offline', '--manifest-path',
                        str(root / 'track-b/Cargo.toml')], cwd=root / 'track-b', env=env, check=True)
        binary = target / 'release/solution'
    env = dict(os.environ, B_RUST_BINARY=str(binary))
    subprocess.run([sys.executable, str(root / 'experiments/b-bounded-boundary.py'),
                    str(root / 'experiments/b-rust-positional-adapter.py')], cwd=root, env=env, check=True)
