from pathlib import Path
import subprocess,tempfile
root=Path(__file__).resolve().parents[2]
with tempfile.TemporaryDirectory() as d:
    src=Path(d)/'main.rs'; exe=Path(d)/'test'
    src.write_text((root/'experiments/c-owner-singlemap/candidate.rs').read_text()+'\n'+(Path(__file__).parent/'property-tail.rs').read_text())
    subprocess.run(['rustc','--edition=2021','--test','-O','-C','overflow-checks=yes',str(src),'-o',str(exe)],check=True)
    subprocess.run([str(exe),'--nocapture'],check=True)
