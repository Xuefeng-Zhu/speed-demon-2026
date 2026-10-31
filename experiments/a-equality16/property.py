#!/usr/bin/env python3
"""Test the exact candidate endpoint equality code on lengths, alignments and mismatches."""
from pathlib import Path
import subprocess
import tempfile

source = Path(__file__).with_name('candidate.rs').read_text()
tests = r'''
#[cfg(test)] mod property {
 use super::*;
 #[test] fn endpoint_equality_alignments_and_mismatches() {
  for n in 0usize..=125 { for aa in 0..8 { for bb in 0..8 {
    let a=16+aa; let b=224+bb; let mut data=vec![0x5au8;512];
    for i in 0..n { let v=(i.wrapping_mul(47).wrapping_add(n)) as u8; data[a+i]=v; data[b+i]=v; }
    assert!(same(&data,a,b,n),"same n={n} a={aa} b={bb}");
    for i in 0..n { data[b+i]^=1; assert!(!same(&data,a,b,n),"diff n={n} a={aa} b={bb} i={i}"); data[b+i]^=1; }
  } } }
 }
}
'''
with tempfile.TemporaryDirectory(prefix='a-equality-property-') as tmp:
    root = Path(tmp); src=root/'main.rs'; exe=root/'test'
    src.write_text(source+tests)
    subprocess.run(['rustc','--edition=2021','--test','-O','-C','overflow-checks=yes',str(src),'-o',str(exe)],check=True)
    subprocess.run([str(exe)],check=True)
