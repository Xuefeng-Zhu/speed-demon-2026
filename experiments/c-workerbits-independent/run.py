from pathlib import Path
import hashlib,subprocess,tempfile
p=Path(__file__).resolve().parent
src=p.parent/'c-direct-workerbits/candidate.rs'
b=src.read_bytes();sha=hashlib.sha256(b).hexdigest()
assert sha=='f2b9e6bc60da6fd12778580bd7cc9371b21a269f49758df76f07af82894c2164',sha
with tempfile.TemporaryDirectory(prefix='workerbits-independent-') as d:
 path=Path(d)/'test.rs';exe=Path(d)/'test';path.write_bytes(b+b'\n'+(p/'tail.rs').read_bytes())
 subprocess.run(['rustc','--edition=2021','--test','-O','-C','overflow-checks=yes',str(path),'-o',str(exe)],check=True,timeout=60)
 subprocess.run([str(exe),'independent_workerbits','--nocapture'],check=True,timeout=90)
