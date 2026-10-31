#!/usr/bin/env python3
"""Exercise exact shortcut implementation with mostly-unpinned graph vertices."""
from pathlib import Path
import subprocess,tempfile
src=Path(__file__).with_name('meeting.rs').read_text()
tail=r'''
#[cfg(test)] mod independent_shortcuts {
 use super::*;
 const INF:u64=u64::MAX;
 fn graphs(n:usize, es:&[(u32,u32,u32)]) -> [Csr;2] {
  fn one(n:usize,es:&[(u32,u32,u32)],reverse:bool)->Csr {
   let mut f=vec![0u32;n+1];
   for &(u,v,_) in es {let x=if reverse {v} else {u}; f[x as usize+1]+=1;}
   for i in 0..n {f[i+1]+=f[i];}
   let mut c=f[..n].to_vec(); let mut a=vec![0u64;es.len()];
   for &(u,v,w) in es {let (x,y)=if reverse {(v,u)} else {(u,v)};let i=c[x as usize] as usize;a[i]=(w as u64)<<32|y as u64;c[x as usize]+=1;}
   Csr{first:f,adj:a}
  }
  [one(n,es,false),one(n,es,true)]
 }
 fn expected(n:usize,es:&[(u32,u32,u32)],s:u32,t:u32)->u64 {
  let mut d=vec![INF;n];d[s as usize]=0;
  for _ in 0..n {let mut changed=false;for &(u,v,w) in es {let x=d[u as usize];if x!=INF && x+(w as u64)<d[v as usize] {d[v as usize]=x+w as u64;changed=true;}}if !changed {break;}}
  d[t as usize]
 }
 fn run(n:usize,es:&[(u32,u32,u32)],qs:&[(u32,u32)],threads:usize)->bool {
  let [mut f,mut b]=graphs(n,es);let original_f=f.adj.clone();let original_b=b.adj.clone();
  let l=links([&f,&b],qs,threads);shorten_both(&mut f,&mut b,&l,threads);
  for &(s,t) in qs {let x=Search::new(n).distance([&f,&b],s,t);let y=expected(n,es,s,t);assert_eq!(x,y,"n={n} t={threads} s={s} t={t} es={es:?}");}
  f.adj!=original_f || b.adj!=original_b
 }
 #[test] fn random_sparse_mostly_unpinned() {
  let mut z=0xf38a59ce619d1234u64;fn r(z:&mut u64)->u64 {*z^=*z<<13;*z^=*z>>7;*z^=*z<<17;*z}
  let weights=[0,1,2,17,u32::MAX,u32::MAX-1];let mut rewrites=0;
  for case in 0..1200 {
   let n=2+(r(&mut z)%15) as usize;let mut es=Vec::new();
   for i in 0..n-1 {
    let mode=r(&mut z)%4;let w=weights[(r(&mut z) as usize)%weights.len()];let q=weights[(r(&mut z) as usize)%weights.len()];
    if mode&1!=0 {es.push((i as u32,(i+1) as u32,w));if r(&mut z)%4==0 {es.push((i as u32,(i+1) as u32,q));}}
    if mode&2!=0 {es.push(((i+1) as u32,i as u32,q));}
    if r(&mut z)%7==0 {es.push((i as u32,i as u32,w));}
   }
   if case%4==0 {let u=(r(&mut z)%n as u64) as u32;let v=(r(&mut z)%n as u64) as u32;es.push((u,v,weights[(r(&mut z) as usize)%weights.len()]));}
   let s=(r(&mut z)%n as u64) as u32;let t=(r(&mut z)%n as u64) as u32;
   for workers in [1,2,7] {if run(n,&es,&[(s,t)],workers) {rewrites+=1;}}
  }
  assert!(rewrites>100,"no effective shortcuts exercised: {rewrites}"); eprintln!("random shortcuts {rewrites}");
 }
 #[test] fn random_reachable_directed_chains() {
  let mut z=0x73646b912774832du64;fn r(z:&mut u64)->u64 {*z^=*z<<13;*z^=*z>>7;*z^=*z<<17;*z}
  let mut rewrites=0;
  for case in 0..1024 {
   let n=3+(r(&mut z)%65) as usize;let mut es=Vec::new();
   for i in 0..n-1 {
    let v=if case%4==0 && i==n/2 {u32::MAX} else {(r(&mut z)%30) as u32};
    es.push((i as u32,(i+1) as u32,v));
    if r(&mut z)%3==0 {es.push((i as u32,(i+1) as u32,v.saturating_add((r(&mut z)%7) as u32)));}
    if r(&mut z)%2==0 {es.push(((i+1) as u32,i as u32,(r(&mut z)%25) as u32));}
    if r(&mut z)%5==0 {es.push((i as u32,i as u32,0));}
   }
   if case%3==0 {es.push(((n-1) as u32,0,(r(&mut z)%30) as u32));}
   let mut qs=vec![(0,(n-1) as u32)];if case%5==0 {qs.push(((n/2) as u32,(n-1) as u32));}
   for workers in [1,2,7] {if run(n,&es,&qs,workers) {rewrites+=1;}}
  }
  assert!(rewrites>500,"too few reachable shortcuts: {rewrites}"); eprintln!("reachable shortcuts {rewrites}");
 }
 #[test] fn exhaustive_directed_four_node_chains() {
  let arcs=[(0u32,1u32),(1,0),(1,2),(2,1),(2,3),(3,2)];
  let values=[None,Some(0u32),Some(1u32),Some(u32::MAX)];
  let mut rewrites=0usize;
  for code in 0..4096usize {
   let mut es=Vec::new();let mut z=code;
   for &(u,v) in &arcs {if let Some(w)=values[z%4] {es.push((u,v,w));} z/=4;}
   for extra in 0..4 {
    let mut g=es.clone();
    if extra&1!=0 {g.push((0,1,1));g.push((0,1,u32::MAX));}
    if extra&2!=0 {g.push((2,3,0));g.push((2,3,u32::MAX));}
    if run(4,&g,&[(0,3),(3,0)],2) {rewrites+=1;}
   }
  }
  assert!(rewrites>1000,"too few exhaustive rewrites: {rewrites}"); eprintln!("exhaustive 4-node shortcuts {rewrites}");
 }
 #[test] fn boundaries_parallel_and_pins() {
  // Ensure both sides preserve minimum shortcut with unequal parallel edges.
  let es=vec![(0,1,1),(0,1,9),(1,2,2),(1,2,3),(2,3,4),(2,3,5)];
  assert!(run(4,&es,&[(0,3)],7));
  let [mut f,mut b]=graphs(4,&es);let l=links([&f,&b],&[(0,3)],7);shorten_both(&mut f,&mut b,&l,7);
  assert_eq!(f.edges(0).filter(|&(v,_)|v==3).map(|(_,w)|w).min(),Some(7));
  assert_eq!(b.edges(3).filter(|&(v,_)|v==0).map(|(_,w)|w).min(),Some(7));
  // Exact max edge is present, not confused with a missing edge; overflow falls back.
  let es=vec![(0,1,u32::MAX),(1,2,0)];assert!(run(3,&es,&[(0,2)],2));
  let [mut f,mut b]=graphs(3,&es);let l=links([&f,&b],&[(0,2)],2);shorten_both(&mut f,&mut b,&l,2);assert_eq!(f.edges(0).collect::<Vec<_>>(),vec![(2,u32::MAX as u64)]);
  let es=vec![(0,1,u32::MAX),(1,2,1)];let [mut f,mut b]=graphs(3,&es);let l=links([&f,&b],&[(0,2)],2);shorten_both(&mut f,&mut b,&l,2);assert_eq!(f.edges(0).collect::<Vec<_>>(),vec![(1,u32::MAX as u64)]);assert_eq!(Search::new(3).distance([&f,&b],0,2),u32::MAX as u64+1);
  // Last-allowed 17-edge path shortcuts; longer path retains first edge.
  for n in [18usize,19,36] {let es=(0..n-1).map(|i|(i as u32,i as u32+1,1u32)).collect::<Vec<_>>();let [mut f,mut b]=graphs(n,&es);let q=[(0,(n-1) as u32)];let l=links([&f,&b],&q,7);shorten_both(&mut f,&mut b,&l,7);let first=f.edges(0).next().unwrap();assert_eq!(first.0,if n==18 {(n-1) as u32} else {1});assert_eq!(Search::new(n).distance([&f,&b],0,(n-1) as u32),(n-1) as u64);}
  // The intermediate query endpoint is explicitly pinned.
  let es=(0..9).map(|i|(i as u32,i as u32+1,0u32)).collect::<Vec<_>>();let [mut f,mut b]=graphs(10,&es);let q=[(0,9),(4,9)];let l=links([&f,&b],&q,3);assert_eq!(l[4].neighbors,[u32::MAX;2]);shorten_both(&mut f,&mut b,&l,3);assert_eq!(f.edges(0).next(),Some((4,0)));for &(s,t) in &q{assert_eq!(Search::new(10).distance([&f,&b],s,t),0);}
 }
}
'''
with tempfile.TemporaryDirectory(prefix='d-independent-shortcuts-') as tmp:
 p=Path(tmp);(p/'test.rs').write_text(src+tail)
 subprocess.run(['rustc','--edition=2021','-O','-C','overflow-checks=yes','-C','debug-assertions=yes','--test',str(p/'test.rs'),'-o',str(p/'test')],check=True)
 subprocess.run([str(p/'test'),'--test-threads=1','--nocapture'],check=True)
