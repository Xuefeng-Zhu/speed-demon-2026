#[cfg(test)]
mod independent_forward_prune {
    use super::*;
    use std::sync::atomic::Ordering::Relaxed;

    fn csr(n: usize, edges: &[(usize, usize, u32)], reverse: bool) -> Csr {
        let mut rows = vec![Vec::<(usize,u32)>::new(); n];
        for &(u,v,w) in edges { let (a,b) = if reverse {(v,u)} else {(u,v)}; rows[a].push((b,w)); }
        let mut first = Vec::with_capacity(n+1);
        let mut compact = Vec::new();
        let mut wide = Vec::new();
        for row in rows {
            first.push(compact.len() as u32);
            for (v,w) in row { compact.push((w.min(2047)<<21) | v as u32); wide.push(w); }
        }
        first.push(compact.len() as u32);
        Csr { first, adj: Vec::new(), compact, wide }
    }

    fn check(n: usize, edges: &[(usize,usize,u32)]) {
        let mut expected = vec![vec![NONE; n]; n];
        for (i,row) in expected.iter_mut().enumerate() { row[i]=0; }
        for &(u,v,w) in edges { expected[u][v]=expected[u][v].min(w as u64); }
        for k in 0..n { for i in 0..n { for j in 0..n {
            expected[i][j]=expected[i][j].min(expected[i][k].saturating_add(expected[k][j]));
        } } }
        let graphs=[csr(n,edges,false),csr(n,edges,true)];
        let mut fast=Search32::new(n); let mut wide=Search::new(n);
        for i in 0..n { for j in 0..n {
            let (d,dropped)=fast.distance([&graphs[0],&graphs[1]],i as u32,j as u32);
            let actual=if d < u32::MAX as u64 || !dropped { d } else { wide.distance([&graphs[0],&graphs[1]],i as u32,j as u32) };
            assert_eq!(actual,expected[i][j],"n={n}, query={i}->{j}, edges={edges:?}");
            assert!(fast.touched.is_empty() && fast.dist.iter().all(|x| *x==[0,0]));
            assert!(fast.heaps.iter().all(|h| h.count==0 && h.nodes.is_empty() && h.head.iter().all(|&x| x==END)));
            assert!(wide.touched.is_empty() && wide.dist.iter().all(|x| *x==[0,0]));
            assert!(wide.heaps.iter().all(|h| h.count==0 && h.links.iter().all(|x| x[1]==UNLINKED)));
        } }
    }

    #[test]
    fn exhaustive_and_random_graphs() {
        let weights=[None,Some(0),Some(1),Some(u32::MAX)];
        let pairs=[(0,1),(0,2),(1,0),(1,2),(2,0),(2,1)];
        for bits in 0..4096usize {
            let mut edges=Vec::new();
            for (j,&(u,v)) in pairs.iter().enumerate() { if let Some(w)=weights[(bits>>(2*j))&3] { edges.push((u,v,w)); } }
            check(3,&edges);
        }
        let mut seed=0x92345678ab56cd12u64;
        let mut rnd=|| {seed^=seed<<7;seed^=seed>>9;seed^=seed<<8;seed};
        let palette=[0,0,1,2,3,100,2046,2047,u32::MAX/2,u32::MAX-2,u32::MAX-1,u32::MAX];
        for _ in 0..12000 {
            let n=2+(rnd()%7) as usize; let mut edges=Vec::new();
            for u in 0..n { for v in 0..n { if rnd()%4==0 {
                let w=palette[(rnd() as usize)%palette.len()]; edges.push((u,v,w));
                if rnd()%17==0 { edges.push((u,v,palette[(rnd() as usize)%palette.len()])); }
            } } }
            check(n,&edges);
        }
        eprintln!("COUNTERS prune={} known_lt_b={} known_ge_b={} unseen={} zero_b={} meeting_improved={} f_empty={} r_empty={} cutoff={} exhausted={}",
            P_PRUNE.load(Relaxed), P_KNOWN_LT.load(Relaxed), P_KNOWN_GE.load(Relaxed), P_UNSEEN.load(Relaxed), P_ZERO_B.load(Relaxed), P_IMPROVE.load(Relaxed), P_FEMPTY.load(Relaxed), P_REMPTY.load(Relaxed), P_CUTOFF.load(Relaxed), P_EXHAUST.load(Relaxed));
        if POOL_CAP > 2 { assert!(P_PRUNE.load(Relaxed)>0); }
    }
}
