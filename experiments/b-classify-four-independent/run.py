#!/usr/bin/env python3
"""Run exact-source tokenizer properties; optional Linux x86-v3 execution."""
import hashlib
import platform
import subprocess
import sys
import tempfile
from pathlib import Path

root = Path(__file__).resolve().parents[2]
candidate = root / 'experiments/b-classify-four-current/candidate.rs'
source = candidate.read_text()
assert hashlib.sha256(source.encode()).hexdigest() == '7ffd820e9cfebdd93c515edc9a721c54328f04a7b470490d953df1bf93fd0142'
tails = [(root/'experiments/b-avx-transitions/token-tail.rs').read_text(),
         (Path(__file__).parent/'boundary-tail.rs').read_text()]
actual = '--x86-v3' in sys.argv[1:]
if actual:
    if platform.system() != 'Linux' or platform.machine() not in ('x86_64', 'amd64'):
        raise SystemExit('--x86-v3 requires Linux x86-64')
    features = set(Path('/proc/cpuinfo').read_text().lower().split('flags', 1)[1].splitlines()[0].split())
    need = {'avx', 'avx2', 'bmi1', 'bmi2', 'f16c', 'fma', 'movbe', 'pni', 'popcnt',
            'sse4_1', 'sse4_2', 'ssse3', 'xsave', 'cx16', 'lahf_lm'}
    if not need <= features:
        raise SystemExit('x86-64-v3 preflight missing: ' + ', '.join(sorted(need-features)))
    if not ({'abm', 'lzcnt'} & features):
        raise SystemExit('x86-64-v3 preflight missing: lzcnt/abm')
with tempfile.TemporaryDirectory(prefix='b-four-independent-') as tmp:
    path = Path(tmp)/'property.rs'; binary = Path(tmp)/'property'
    path.write_text(source + '\n' + '\n'.join(tails))
    cmd = ['rustc', '--edition=2021', '--test', '-O', '-C', 'overflow-checks=yes',
           '-C', 'debug-assertions=yes']
    if actual: cmd += ['-C', 'target-cpu=x86-64-v3']
    subprocess.run([*cmd, str(path), '-o', str(binary)], check=True)
    result = subprocess.run([str(binary), '--nocapture'], text=True, capture_output=True, check=True)
    print(result.stdout)
    if actual and 'independent_transition::actual_avx2_enabled ... ok' not in result.stdout:
        raise SystemExit('actual AVX2 test did not run')
