from pathlib import Path
import subprocess,tempfile
p=Path(__file__).resolve().parent
with tempfile.TemporaryDirectory(prefix='c-radix-property-') as t:
 out=Path(t)/'main.rs';binary=Path(t)/'test'
 out.write_text((p/'candidate.rs').read_text()+'\n'+(p/'property-tail.rs').read_text())
 subprocess.run(['rustc','--edition=2021','--test','-O','-C','overflow-checks=yes','-C','debug-assertions=yes',str(out),'-o',str(binary)],check=True)
 subprocess.run([str(binary)],check=True)
