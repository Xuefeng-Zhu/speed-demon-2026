#!/usr/bin/env python3
"""Inspect the exact transformed CSR across chain and fallback boundaries."""
from pathlib import Path
import subprocess,tempfile
source=Path(__file__).with_name('meeting.rs').read_text()
tests=r'''
#[cfg(test)] mod boundary {
 use super::*;
 fn graph(n:usize, es:&[(u32,u32,u32)]) -> Csr {
  let mut rows=vec![Vec::new();n];for &(u,v,w) in es {rows[u as usize].push((w as u64)<<32 | v as u64);}
  let mut first=vec![0u32];let mut adj=Vec::new();for row in rows {adj.extend(row);first.push(adj.len() as u32);}Csr{first,adj}
 }
 fn run(n:usize, es:&[(u32,u32,u32)], q:&[(u32,u32)])->[Csr;2] {
  let rev:Vec<_>=es.iter().map(|&(u,v,w)|(v,u,w)).collect();
  let mut f=graph(n,es);let mut b=graph(n,&rev);let link=links([&f,&b],q,7);
  shorten_both(&mut f,&mut b,&link,7);[f,b]
 }
 fn edge(g:&Csr,u:u32)->Vec<(u32,u64)>{g.edges(u).collect()}
 #[test] fn lengths_and_fallback() {
  for n in [16,17,18,19,34] {
   let es:Vec<_>=(0..n-1).map(|u|(u as u32,(u+1)as u32,1)).collect();
   let [f,b]=run(n,&es,&[(0,(n-1)as u32)]);
   let want=if n<=18 {((n-1)as u32,(n-1)as u64)} else {(1,1)};
   assert_eq!(edge(&f,0),vec![want]);
   let want_back=if n<=18 {(0,(n-1)as u64)} else {((n-2)as u32,1)};
   assert_eq!(edge(&b,(n-1)as u32),vec![want_back]);
  }
 }
 #[test] fn pins_missing_duplicates_zero_and_overflow() {
  let [f,_]=run(4,&[(0,1,1),(1,2,2),(2,3,3)],&[(0,3),(1,3)]);
  assert_eq!(edge(&f,0),vec![(1,1)]); // pinned intermediate
  let [f,_]=run(3,&[(0,1,2),(2,1,4)],&[(0,2)]);
  assert_eq!(edge(&f,0),vec![(1,2)]); // missing forward arc
  let [f,_]=run(3,&[(0,1,u32::MAX),(1,2,1)],&[(0,2)]);
  assert_eq!(edge(&f,0),vec![(1,u32::MAX as u64)]); // sum does not fit u32
  let [f,_]=run(3,&[(0,1,0),(1,2,u32::MAX),(1,2,0),(1,2,5)],&[(0,2)]);
  assert_eq!(edge(&f,0),vec![(2,0)]); // zero beats max among parallel edges
  let [f,_]=run(4,&[(0,1,0),(1,2,0),(2,0,0)],&[(0,3)]);
  assert_eq!(edge(&f,0),vec![(0,0)]); // degree-two zero cycle returns to core
 }
}
'''
with tempfile.TemporaryDirectory(prefix='d-shortcut-boundaries-') as tmp:
 p=Path(tmp);(p/'test.rs').write_text(source+tests)
 subprocess.run(['rustc','--edition=2021','-O','-C','overflow-checks=yes','-C','debug-assertions=yes','--test',str(p/'test.rs'),'-o',str(p/'test')],check=True)
 subprocess.run([str(p/'test'),'--test-threads=1'],check=True)
