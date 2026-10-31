#!/usr/bin/env python3
"""Test exact sparse table with hash collisions, growth and generation wrap."""
from pathlib import Path
import subprocess,tempfile
source=Path(__file__).with_name('meeting.rs').read_text()
tail=r'''
#[cfg(test)] mod table_tests {
 use super::*;
 #[test] fn collisions_growth_and_wrap() {
  let mut m=Sparse::new();m.begin();let bucket=m.hash(0)&1023;let mut keys=Vec::new();
  for v in 0..1_740_512u32 {if m.hash(v)&1023==bucket {keys.push(v);if keys.len()==700 {break;}}}
  assert!(keys.len()==700);
  for (i,&v) in keys.iter().enumerate() {let s=m.slot(v);s[0]=!(i as u64);s[1]=!(u32::MAX as u64+i as u64);}
  assert!(m.cells.len()>1024);
  for (i,&v) in keys.iter().enumerate() {assert_eq!(m.get(v),[!(i as u64),!(u32::MAX as u64+i as u64)]);}
  m.gen=u32::MAX-1;m.begin();assert_eq!(m.gen,u32::MAX);*m.slot(42)=[7,9];assert_eq!(m.get(42),[7,9]);
  m.begin();assert_eq!(m.gen,1);assert_eq!(m.get(42),[0,0]);*m.slot(42)=[11,13];assert_eq!(m.get(42),[11,13]);
  for _ in 0..500 {m.begin();for &v in keys.iter().take(50){*m.slot(v)=[!1,!2];}for &v in keys.iter().take(50){assert_eq!(m.get(v),[!1,!2]);}}
 }
}
'''
with tempfile.TemporaryDirectory(prefix='d-sparse-table-') as tmp:
 p=Path(tmp);(p/'test.rs').write_text(source+tail)
 subprocess.run(['rustc','--edition=2021','-O','-C','overflow-checks=yes','-C','debug-assertions=yes','--test',str(p/'test.rs'),'-o',str(p/'test')],check=True)
 subprocess.run([str(p/'test')],check=True)
