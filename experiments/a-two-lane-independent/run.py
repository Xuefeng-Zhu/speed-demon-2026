#!/usr/bin/env python3
"""Compile the exact candidate with an independent direct-parse property."""
from pathlib import Path
import hashlib
import subprocess
import tempfile

here = Path(__file__).resolve().parent
candidate = here.parent / 'a-two-lane-interleaved' / 'candidate.rs'
source = candidate.read_text()
expected = 'b98d76ca3d17b959c43c01c33c227d9614196710d4733a68be1b03829c560b0c'
assert hashlib.sha256(source.encode()).hexdigest() == expected
marker = '    fn find(&mut self, d: &[u8], h: u64, s: usize, e: usize) -> usize {'
assert source.count(marker) == 1
wrapping = {
    '    v = v * 10 + (v >> 8);': '    v = v.wrapping_mul(10).wrapping_add(v >> 8);',
    '    let lo = (v & 0x0000_00FF_0000_00FF) * (100 + (1_000_000 << 32));':
        '    let lo = (v & 0x0000_00FF_0000_00FF).wrapping_mul(100 + (1_000_000 << 32));',
    '    let hi = ((v >> 16) & 0x0000_00FF_0000_00FF) * (1 + (10_000 << 32));':
        '    let hi = ((v >> 16) & 0x0000_00FF_0000_00FF).wrapping_mul(1 + (10_000 << 32));',
}
with tempfile.TemporaryDirectory(prefix='sd-a-lane-independent-') as td:
    root = Path(td)
    for checked in (False, True):
        for collision in (False, True):
            body = source.replace(marker, marker + '\n        let h = 0u64;') if collision else source
            if checked:
                for old, new in wrapping.items():
                    assert body.count(old) == 1
                    body = body.replace(old, new)
            label = ('checked' if checked else 'release') + ('-zero' if collision else '-normal')
            path, binary = root / (label + '.rs'), root / label
            path.write_text(body + '\n' + (here / 'property-tail.rs').read_text())
            subprocess.run(['rustc', '--edition=2021', '--test', '-O', '-C',
                            'overflow-checks=' + ('yes' if checked else 'no'),
                            '-C', 'debug-assertions=yes', path, '-o', binary], check=True)
            subprocess.run([binary, '--test-threads=1'], check=True)
            print('PASS direct-parse intervals:', label, flush=True)
