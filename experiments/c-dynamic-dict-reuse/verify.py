#!/usr/bin/env python3
"""Test reference equivalence, equal-hash and per-partition reset properties."""
from pathlib import Path
import subprocess, sys, tempfile
here=Path(__file__).resolve().parent
source=(here/'candidate.rs').read_text()
needle='let (name, name_len, h) = field_name_hash(recs, &mut p);'
assert source.count(needle)==1
with tempfile.TemporaryDirectory(prefix='c-reuse-check-') as tmp:
 root=Path(tmp)
 test=root/'prop.rs'; test.write_text(source+'\n'+(here/'property-tail.rs').read_text())
 subprocess.run(['rustc','--edition=2021','-O','-C','overflow-checks=yes','-C','debug-assertions=yes','--test',str(test),'-o',str(root/'prop')],check=True)
 subprocess.run([str(root/'prop')],check=True)
 subprocess.run([sys.executable,str(here/'reference.py'),'--source',str(here/'candidate.rs'),'--seeds','24'],check=True)
 forced=root/'forced.rs'; forced.write_text(source.replace(needle,'let (name, name_len, _h) = field_name_hash(recs, &mut p); let h = 0u64;'))
 subprocess.run([sys.executable,str(here/'reference.py'),'--source',str(forced),'--seeds','8'],check=True)
