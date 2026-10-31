#!/usr/bin/env python3
"""Compile exact source and verify runtime permutation + CSR as graph multiset."""
from pathlib import Path
import subprocess,tempfile
source=Path(__file__).with_name('meeting.rs').read_text()
tail=r'''
#[cfg(test)] mod independent_cluster_review {
 use super::*;
 fn graphs(n:usize, es:&[(u32,u32,u32)])->[Csr;2] {
  fn one(n:usize,es:&[(u32,u32,u32)],reverse:bool)->Csr {
   let mut f=vec![0u32;n+1];
   for &(u,v,_) in es {let x=if reverse {v} else {u};f[x as usize+1]+=1;}
   for i in 0..n {f[i+1]+=f[i];}
   let mut next=f[..n].to_vec();let mut a=vec![0u64;es.len()];
   for &(u,v,w) in es {let (x,y)=if reverse {(v,u)} else {(u,v)};let i=next[x as usize] as usize;a[i]=(w as u64)<<32|y as u64;next[x as usize]+=1;}
   Csr{first:f,adj:a}
  }
  [one(n,es,false),one(n,es,true)]
 }
 fn check(n:usize,es:&[(u32,u32,u32)],workers:usize) {
  let (g,map)=relabel(graphs(n,es),workers);assert_eq!(map.len(),n);
  let mut inverse=vec![u32::MAX;n];
  for (old,&new) in map.iter().enumerate() {assert!((new as usize)<n);assert_eq!(inverse[new as usize],u32::MAX,"duplicate mapped ID");inverse[new as usize]=old as u32;}
  assert!(inverse.iter().all(|&u|u!=u32::MAX));
  let mut original=[vec![Vec::new();n],vec![Vec::new();n]];
  for &(u,v,w) in es {original[0][u as usize].push((map[v as usize],w as u64));original[1][v as usize].push((map[u as usize],w as u64));}
  for side in 0..2 {assert_eq!(g[side].first.len(),n+1);assert_eq!(g[side].adj.len(),es.len());
   for old in 0..n {let mut expected=original[side][old].clone();let mut got=g[side].edges(map[old]).collect::<Vec<_>>();expected.sort_unstable();got.sort_unstable();assert_eq!(got,expected,"n={n} side={side} old={old} workers={workers}");}
  }
 }
 #[test] fn empty_and_chunk_boundaries() {
  for n in [1,2,3,7,31,255,256,257,511,512,513] {for workers in [1,2,3,7,32] {check(n,&[],workers);}}
 }
 #[test] fn stars_chains_duplicates_and_races() {
  for n in [2usize,3,17,255,256,257,513] {
   let mut es=Vec::new();for i in 1..n as u32 {
    es.push((0,i,if i%2==0 {0}else{u32::MAX}));
    if i%3!=0 {es.push((i,0,i));} if i%5==0 {es.push((0,i,0));}
    es.push((i,i,0));if i>1 {es.push((i-1,i,i));}
   }
   for workers in [1,2,3,7,32] {for _ in 0..3 {check(n,&es,workers);}}
  }
 }
 #[test] fn random_multigraphs() {
  let mut z=0x24c7ad31985fa0e1u64;fn r(z:&mut u64)->u64 {*z^=*z<<13;*z^=*z>>7;*z^=*z<<17;*z}
  for case in 0..160 {let n=1+(r(&mut z)%96) as usize;let m=(r(&mut z)%400) as usize;let mut es=Vec::new();
   for i in 0..m {let u=(r(&mut z)%n as u64)as u32;let v=(r(&mut z)%n as u64)as u32;let w=match i%5 {0=>0,1=>u32::MAX,_=>r(&mut z)as u32};es.push((u,v,w));if i%11==0 {es.push((u,v,w));}}
   let workers=[1,2,3,7,32][case%5];check(n,&es,workers);
  }
 }
}
'''
with tempfile.TemporaryDirectory(prefix='d-cluster-review-') as tmp:
 p=Path(tmp);(p/'test.rs').write_text(source+tail)
 subprocess.run(['rustc','--edition=2021','-O','-C','overflow-checks=yes','-C','debug-assertions=yes','--test',str(p/'test.rs'),'-o',str(p/'test')],check=True)
 subprocess.run([str(p/'test'),'--test-threads=1'],check=True)
