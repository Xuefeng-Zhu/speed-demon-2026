#[cfg(test)] mod force_cap {
 use super::*;
 fn csr(n:usize, edges:&[(usize,u32,u64)])->Csr {
  let mut first=vec![0;n+1];for &(u,_,_) in edges {first[u+1]+=1;}for u in 0..n {first[u+1]+=first[u];}
  let mut cur=first[..n].to_vec();let mut adj=vec![0;edges.len()];for &(u,v,w) in edges {adj[cur[u] as usize]=(w<<32)|v as u64;cur[u]+=1;}
  Csr{first,adj,compact:Vec::new(),wide:Vec::new()}
 }
 #[test] fn pool_exhaustion_cleans_and_forces_wide() {
  assert!(POOL_CAP<=2);
  let f=csr(6,&[(0,1,1),(0,2,2),(0,3,3),(0,4,4),(0,5,5)]);
  let b=csr(6,&[(1,0,1),(2,0,2),(3,0,3),(4,0,4),(5,0,5)]);
  let mut q=Search32::new(6);let mut wide=Search::new(6);
  for _ in 0..100 {
   assert_eq!(q.distance([&f,&b],0,0),(0,false));
   assert_eq!(q.distance([&f,&b],0,5),(NONE,true));
   assert_eq!(wide.distance([&f,&b],0,5),5);
   assert!(q.touched.is_empty());assert!(q.dist.iter().all(|x|*x==[0;2]));assert_eq!(q.heaps[0].count+q.heaps[1].count,0);
  }
 }
}
