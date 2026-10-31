from pathlib import Path
import subprocess, tempfile
root = Path(__file__).resolve().parent
source = (root / 'candidate.rs').read_text()
tail = (root / 'property-tail.rs').read_text()
forced = source.replace('Self::short_hash(k.0[0] ^ k.0[1].rotate_left(29))', '0usize').replace('Self::short_hash(a ^ b.rotate_left(29))', '0usize')
assert forced != source
with tempfile.TemporaryDirectory() as td:
    for label, body, cfg in [('normal', source, []), ('forced', forced, ['--cfg', 'medium_forced'])]:
        path = Path(td) / (label + '.rs'); binary = Path(td) / label
        path.write_text(body + tail)
        subprocess.run(['rustc', '--edition=2021', '--test', '-C', 'opt-level=2', '-C', 'overflow-checks=yes', *cfg, str(path), '-o', str(binary)], check=True)
        subprocess.run([str(binary)], check=True)
