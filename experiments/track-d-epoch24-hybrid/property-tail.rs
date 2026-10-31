
#[cfg(test)]
mod epoch24_property {
    use super::*;
    use std::cmp::Reverse;
    use std::collections::BinaryHeap;

    fn graph(n: usize, edges: &[(u32, u32, u32)], reverse: bool) -> Csr {
        let mut rows = vec![Vec::<(u32,u32)>::new(); n];
        for &(u,v,w) in edges { let (a,b) = if reverse {(v,u)} else {(u,v)}; rows[a as usize].push((b,w)); }
        let mut first=Vec::with_capacity(n+1); let mut adj=Vec::new(); first.push(0);
        for row in rows { for (v,w) in row {adj.push(((w as u64)<<32)|u64::from(v));} first.push(adj.len() as u32); }
        Csr{first,adj,compact:Vec::new(),wide:Vec::new()}
    }
    fn reference(n: usize, edges: &[(u32,u32,u32)], s:u32, t:u32)->u64 {
        let mut rows=vec![Vec::<(u32,u32)>::new();n];
        for &(u,v,w) in edges {rows[u as usize].push((v,w));}
        let mut dist=vec![u64::MAX;n]; let mut q=BinaryHeap::new(); dist[s as usize]=0; q.push(Reverse((0u64,s)));
        while let Some(Reverse((d,u)))=q.pop() {
            if d!=dist[u as usize] {continue;} if u==t {return d;}
            for &(v,w) in &rows[u as usize] {let nd=d+u64::from(w); if nd<dist[v as usize] {dist[v as usize]=nd;q.push(Reverse((nd,v)));}}
        }
        u64::MAX
    }
    fn answer(fast:&mut Search32, wide:&mut Search, f:&Csr,b:&Csr,s:u32,t:u32)->u64 {
        let (v,dropped)=fast.distance([f,b],s,t);
        let out=if v<NARROW_INF || !dropped {v} else {wide.distance([f,b],s,t)};
        for h in &fast.heaps {assert_eq!(h.count,0);assert!(h.head.iter().all(|&x|x==END));}
        out
    }
    #[test]
    fn explicit_cutoff_edges_force_only_safe_results_and_clean_reuse() {
        let n=12;
        let edges=[(0,1,(NARROW_INF-1) as u32), (2,3,NARROW_INF as u32),
            (4,5,(NARROW_INF+1) as u32), (6,7,u32::MAX),
            (8,9,(NARROW_INF-1) as u32), (9,10,1), (8,10,(NARROW_INF+2) as u32)];
        let f=graph(n,&edges,false); let b=graph(n,&edges,true);
        let mut fast=Search32::new(n); let mut wide=Search::new(n);
        let cases=[(0,1,NARROW_INF-1),(2,3,NARROW_INF),(4,5,NARROW_INF+1),
            (6,7,u32::MAX as u64),(8,10,NARROW_INF),(0,11,u64::MAX),(3,3,0)];
        for _ in 0..6 { for &(s,t,expected) in &cases {
            assert_eq!(answer(&mut fast,&mut wide,&f,&b,s,t),expected,"{s}->{t}");
        }}
        if POOL_CAP>0 {
            let (narrow,dropped)=fast.distance([&f,&b],2,3);
            assert_eq!(narrow,u64::MAX); assert!(dropped,"cutoff edge must be marked discarded");
        }
    }
    #[test]
    fn cutoff_pool_reuse_and_epoch_wrap_match_independent_dijkstra() {
        let mut seed=0x943e_18b3_17d2_51a7u64;
        let mut next=|| {seed^=seed<<13;seed^=seed>>7;seed^=seed<<17;seed};
        let weights=[0,1,2,127,(NARROW_INF-2) as u32,(NARROW_INF-1) as u32,NARROW_INF as u32,(NARROW_INF+1) as u32,u32::MAX];
        for case in 0..160 {
            let n=2+(next()%19) as usize; let mut edges=Vec::new();
            for _ in 0..(next()%((n*n+1) as u64)) {edges.push(((next()%n as u64) as u32,(next()%n as u64) as u32,weights[(next()%weights.len() as u64) as usize]));}
            let f=graph(n,&edges,false); let b=graph(n,&edges,true);
            let mut fast=Search32::new(n); let mut wide=Search::new(n);
            // Force the next two nontrivial queries across 0xffff -> 1 and
            // seed a stale epoch-1 row to catch wrap without a full reset.
            fast.epoch=u16::MAX-1; fast.dist[0]=(1u64<<48)|1;
            for k in 0..240 {
                let s=if k<3 {0} else {(next()%n as u64) as u32};
                let t=if k<3 {1} else {(next()%n as u64) as u32};
                let got=answer(&mut fast,&mut wide,&f,&b,s,t);
                assert_eq!(got,reference(n,&edges,s,t),"case={case} query={k} s={s} t={t}");
            }
        }
    }
}
