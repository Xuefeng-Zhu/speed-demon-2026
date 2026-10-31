#!/usr/bin/env python3
"""Adapt legacy Track B positional fixtures to a directory-based Rust binary.

Set B_RUST_BINARY to the compiled executable. The fixture calls this script as
    adapter.py /path/to/docs.txt /path/to/queries.txt /path/to/results.txt
"""
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile


def main():
    if len(sys.argv) != 4 or not os.environ.get('B_RUST_BINARY'):
        raise SystemExit('usage: B_RUST_BINARY=/path/to/solution adapter.py DOCS QUERIES RESULTS')
    binary = Path(os.environ['B_RUST_BINARY']).resolve(strict=True)
    docs, queries = (Path(p).resolve(strict=True) for p in sys.argv[1:3])
    output = Path(sys.argv[3]).resolve()
    with tempfile.TemporaryDirectory(prefix='b-rust-positional-') as tmp:
        root = Path(tmp)
        data, out = root / 'data', root / 'out'
        data.mkdir()
        out.mkdir()
        (data / 'docs.txt').symlink_to(docs)
        (data / 'queries.txt').symlink_to(queries)
        env = dict(os.environ, SD_DATA=str(data), SD_OUT=str(out))
        result = subprocess.run([str(binary)], env=env)
        if result.returncode:
            raise SystemExit(result.returncode)
        shutil.copyfile(out / 'results.txt', output)


if __name__ == '__main__':
    main()
