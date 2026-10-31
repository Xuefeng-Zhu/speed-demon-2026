#[cfg(test)]
mod epoch_tests {
 use super::*;
 fn csr(n:usize, edges:&[(usize,u32,u64)])->Csr {
  let mut first=vec![0u32;n+1];
  for &(u,_,_) in edges { first[u+1]+=1; }
  for i in 0..n {first[i+1]+=first[i];}
  let mut cur=first[..n].to_vec();let mut adj=vec![0u64;edges.len()];
  for &(u,v,w) in edges {adj[cur[u] as usize]=(w<<32)|v as u64;cur[u]+=1;}
  Csr{first,adj,compact:Vec::new(),wide:Vec::new()}
 }
 #[test]
 fn wraps_and_reuses_with_exact_fallback() {
  let edges=[(0,1,1),(0,2,2),(0,3,3),(0,4,4),(0,5,5),(1,0,u32::MAX as u64),(5,4,0)];
  let reverse:Vec<_>=edges.iter().map(|&(u,v,w)|(v as usize,u as u32,w)).collect();
  let f=csr(6,&edges);let b=csr(6,&reverse);
  let mut narrow=Search32::new(6);let mut wide=Search::new(6);
  let mut saw_drop=false; let mut previous=0; let mut wraps=0;
  for i in 0..200_000usize {
   let (s,t)=match i%6 {0=>(0,5),1=>(5,0),2=>(1,0),3=>(5,4),4=>(2,2),_=>(3,1)};
   let (d,dropped)=narrow.distance([&f,&b],s,t);
   if dropped {saw_drop=true;}
   let got=if d < u32::MAX as u64 || !dropped {d} else {wide.distance([&f,&b],s,t)};
   let expected=match (s,t) {(0,5)=>5,(5,0)=>NONE,(1,0)=>u32::MAX as u64,(5,4)=>0,(2,2)=>0,(3,1)=>NONE,_=>unreachable!()};
   assert_eq!(got,expected,"case {i} epoch {}",narrow.epoch);
   assert_eq!(narrow.heaps[0].count+narrow.heaps[1].count,0);
   if POOL_CAP>0 && s!=t { if previous==u16::MAX && narrow.epoch==1 {wraps+=1;} assert!(narrow.epoch==1 || narrow.epoch==previous+1); previous=narrow.epoch;}
  }
  assert!(saw_drop);
  if POOL_CAP>0 {assert!(narrow.epoch>1);assert!(wraps>=2,"only {wraps} wraps");}
 }
}
