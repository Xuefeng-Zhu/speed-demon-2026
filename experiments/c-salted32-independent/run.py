import hashlib, pathlib, subprocess, tempfile
root = pathlib.Path(__file__).resolve().parent
src = root.parent / 'c-rowcache-salted32' / 'candidate.rs'
data = src.read_bytes()
assert hashlib.sha256(data).hexdigest() == '5447d5c7d77e616b60c843c20f58cacc6bd152e6c9337e1a417f7b1768d863aa'
with tempfile.TemporaryDirectory(prefix='c-salted32-independent-') as tmp:
    tmp = pathlib.Path(tmp)
    source = tmp / 'test.rs'
    source.write_bytes(data + b'\n' + (root / 'tail.rs').read_bytes())
    subprocess.run(['rustc', '--edition=2021', '--test', '-O', '-C', 'overflow-checks=yes', '-C', 'debug-assertions=yes', str(source), '-o', str(tmp / 'test')], check=True)
    subprocess.run([str(tmp / 'test'), '--nocapture'], check=True)
