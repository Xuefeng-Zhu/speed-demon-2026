from pathlib import Path
import subprocess,tempfile
p=Path(__file__).parent
s=(p.parent/'c-owner-rowcache/candidate.rs').read_text()
tail=(p/'tail.rs').read_text()
with tempfile.TemporaryDirectory(prefix='c-cache-review-') as d:
 for slots in (1,32768):
  source=s.replace('const CACHE_SLOTS: usize = 32768;',f'const CACHE_SLOTS: usize = {slots};')+tail
  src=Path(d)/f'{slots}.rs';bin=Path(d)/f'{slots}'
  src.write_text(source)
  subprocess.run(['rustc','--edition=2021','--test','-O','-C','overflow-checks=yes',str(src),'-o',str(bin)],check=True)
  subprocess.run([str(bin)],check=True,timeout=60)
