from pathlib import Path
import subprocess,sys,tempfile
p=Path(__file__).parent
with tempfile.TemporaryDirectory(prefix='c-singlemap-test-') as tmp:
 src=Path(tmp)/'main.rs';exe=Path(tmp)/'test'
 src.write_text((p/'candidate.rs').read_text()+'\n'+(p/'small-tail.rs').read_text())
 flags=['-C','target-cpu=x86-64-v3'] if '--avx2' in sys.argv else []
 subprocess.run(['rustc','--edition=2021','--test','-O','-C','overflow-checks=yes']+flags+[str(src),'-o',str(exe)],check=True)
 subprocess.run([str(exe)],check=True,timeout=90)
