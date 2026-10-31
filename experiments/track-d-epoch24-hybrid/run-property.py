#!/usr/bin/env python3
"""Exercise the exact candidate with small forced pool capacities, no data retained."""
from pathlib import Path
import subprocess
import tempfile

here = Path(__file__).resolve().parent
source = (here / 'candidate.rs').read_text()
tail = (here / 'property-tail.rs').read_text()
marker = 'const POOL_CAP: usize = 65_536;'
assert source.count(marker) == 1
with tempfile.TemporaryDirectory(prefix='sd-epoch24-') as directory:
    directory = Path(directory)
    for capacity in (0, 1, 2, 65536):
        src = directory / f'cap{capacity}.rs'
        binary = directory / f'cap{capacity}'
        src.write_text(source.replace(marker, f'const POOL_CAP: usize = {capacity};') + '\n' + tail)
        subprocess.run(['rustc', '--edition=2021', '--test', '-O', '-C', 'overflow-checks=yes',
                        '-C', 'debug-assertions=yes', str(src), '-o', str(binary)], check=True)
        subprocess.run([str(binary)], check=True)
