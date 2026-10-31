#!/usr/bin/env python3
"""Assert actual cap 0/1/2 fallback and cleanup in exact batch4/16 copies."""
from pathlib import Path
import hashlib, subprocess, tempfile
p=Path(__file__).resolve().parent
expected={'batch4':'fa36f3bbfa3ec9e6a92fd787ada415c5e257cdf1ea62a2a2fcf23718c3d5c1c0','batch16':'7fd333be25133a78264cb4b84441de46d4c8bcbfd73914af23761f23d8c47f17'}
marker='const POOL_CAP: usize = 65_536;'
tail=(p/'forced-tail.rs').read_text()
with tempfile.TemporaryDirectory(prefix='sd-batch-force-') as td:
 for name,sha in expected.items():
  src=(p/f'{name}.rs').read_text()
  assert hashlib.sha256(src.encode()).hexdigest()==sha and src.count(marker)==1
  for cap in (0,1,2):
   source=Path(td)/f'{name}-{cap}.rs'; binary=Path(td)/f'{name}-{cap}'
   source.write_text(src.replace(marker,f'const POOL_CAP: usize = {cap};')+'\n'+tail)
   subprocess.run(['rustc','--edition=2021','--test','-O','-C','overflow-checks=yes','-C','debug-assertions=yes',str(source),'-o',str(binary)],check=True)
   subprocess.run([str(binary)],check=True)
print('PASS forced fallback and cleanup in batch4 and batch16')
