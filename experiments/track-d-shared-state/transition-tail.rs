#[cfg(test)] mod shared_transition {
    use super::*;
    fn csr(n: usize, edges: &[(usize, u32, u64)]) -> Csr {
        let mut first=vec![0u32;n+1];
        for &(u,_,_) in edges { first[u+1]+=1; }
        for u in 0..n { first[u+1]+=first[u]; }
        let mut cursor=first[..n].to_vec(); let mut adj=vec![0u64;edges.len()];
        for &(u,v,w) in edges { let i=cursor[u] as usize; adj[i]=(w<<32)|v as u64; cursor[u]+=1; }
        Csr {first,adj,compact:Vec::new(),wide:Vec::new()}
    }
    fn query(q:&mut Search32,wide:&mut Option<Search>,graphs:[&Csr;2],s:u32,t:u32)->u64 {
        let (narrow,dropped)=q.distance(graphs,s,t);
        let answer=if narrow<u32::MAX as u64 || !dropped { narrow } else {
            let w=wide.get_or_insert_with(|| Search::new(q.dist.len()/2));
            w.dist=std::mem::take(&mut q.dist); w.touched=std::mem::take(&mut q.touched);
            let answer=w.distance(graphs,s,t);
            q.dist=std::mem::take(&mut w.dist); q.touched=std::mem::take(&mut w.touched);
            answer
        };
        assert!(q.touched.is_empty());
        assert!(q.dist.iter().all(|&v|v==0));
        assert_eq!(q.heaps[0].count+q.heaps[1].count,0);
        if let Some(w)=wide { assert!(w.dist.is_empty() && w.touched.is_empty());
            for h in &w.heaps { assert_eq!(h.count,0); assert!(h.head.iter().all(|&x|x==END));
                assert!(h.links.iter().all(|x|x[1]==UNLINKED)); }
        }
        answer
    }
    #[test] fn alternating_narrow_wide_and_exhaustion() {
        let n=9;
        let e: Vec<(usize,u32,u64)>=vec![(0,1,u32::MAX as u64-1),(1,2,2),
            (3,4,0),(4,5,10),(3,5,20),(6,7,0),(6,8,0),(6,3,1),
            (7,6,u32::MAX as u64),(5,3,7),(8,2,3),(8,8,0)];
        let rev:Vec<_>=e.iter().map(|&(u,v,w)|(v as usize,u as u32,w)).collect();
        let f=csr(n,&e);let b=csr(n,&rev);
        let mut expected=vec![vec![u64::MAX;n];n];
        for (i,row) in expected.iter_mut().enumerate(){row[i]=0;}
        for &(u,v,w) in &e {expected[u][v as usize]=expected[u][v as usize].min(w);}
        for k in 0..n {for i in 0..n {for j in 0..n {
            expected[i][j]=expected[i][j].min(expected[i][k].saturating_add(expected[k][j]));
        }}}
        let mut q=Search32::new(n);let mut wide=None;
        for turn in 0..50 {for k in 0..n*n {
            let s=(k*7+turn)%n;let t=(k*5+turn/2)%n;
            assert_eq!(query(&mut q,&mut wide,[&f,&b],s as u32,t as u32),expected[s][t],"cap={POOL_CAP} turn={turn} s={s} t={t}");
        }}
    }
}
