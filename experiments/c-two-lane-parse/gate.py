#!/usr/bin/env python3
"""Test the exact representability gate at 4GiB and group sentinel edges."""
from pathlib import Path
import subprocess,tempfile
s=(Path(__file__).parent/'candidate.rs').read_text()
a=s.index('const MAX_PACKED_FILE:');b=s.index('/// Reconstructs',a)
body=s[a:b]
main=r'''
fn main() {
 assert!(can_pack(0,0));assert!(can_pack(u32::MAX as usize,65534));
 assert!(!can_pack(0,65535));assert!(!can_pack(0,65536));
 if usize::BITS > 32 {
  let over=(u32::MAX as u64 + 1) as usize;
  assert!(!can_pack(over,0));assert!(!can_pack(over,65534));
 }
 println!("PASS exact 4GiB/group representability gate boundaries");
}
'''
with tempfile.TemporaryDirectory(prefix='c-pack-gate-') as td:
 p=Path(td);(p/'main.rs').write_text(body+main)
 subprocess.run(['rustc','--edition=2021','-O','-C','overflow-checks=yes',str(p/'main.rs'),'-o',str(p/'main')],check=True)
 subprocess.run([str(p/'main')],check=True)
