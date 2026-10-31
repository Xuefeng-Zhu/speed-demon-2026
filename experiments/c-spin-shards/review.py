#!/usr/bin/env python3
"""Independently stress the exact source guard, auto traits, and unwind behavior."""
from pathlib import Path
import subprocess,tempfile
here=Path(__file__).parent
s=(here/'candidate.rs').read_text()
a=s.index('struct Spin<');b=s.index('/// One of 1024 shards',a);spin=s[a:b]
header='use std::{sync::atomic::{AtomicBool, Ordering}, thread};\n'
with tempfile.TemporaryDirectory(prefix='c-spin-review-') as tmp:
 p=Path(tmp); (p/'main.rs').write_text(header+spin+'\n'+(here/'review-tail.rs').read_text())
 subprocess.run(['rustc','--edition=2021','-O','-C','panic=unwind','-C','overflow-checks=yes',str(p/'main.rs'),'-o',str(p/'main')],check=True)
 subprocess.run([str(p/'main')],check=True,timeout=60)
 (p/'negative.rs').write_text(header+spin+"\nfn assert_sync<T: Sync>() {}\nfn main() { assert_sync::<Held<'static, std::cell::Cell<u64>>>(); }\n")
 r=subprocess.run(['rustc','--edition=2021',str(p/'negative.rs'),'-o',str(p/'negative')],text=True,capture_output=True)
 if r.returncode==0 or 'cannot be shared between threads safely' not in r.stderr: print(r.stderr);raise SystemExit('FAIL: guard !Sync not enforced')
 print('PASS: Held<Cell<u64>> is not Sync')
