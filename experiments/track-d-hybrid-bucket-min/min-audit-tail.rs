#[cfg(test)] mod min_audit {
    use super::*;
    use std::collections::BTreeMap;
    fn audit(h: &FastHeap) {
        for b in 0..65 {
            let mut id=h.head[b]; let mut low=u64::MAX; let mut seen=0;
            while id!=END {
                let x=h.nodes[id as usize]; assert_eq!(h.slot(x.key),b); low=low.min(x.key);
                id=x.next; seen+=1; assert!(seen<=h.nodes.len());
            }
            assert_eq!(h.min[b],low,"bucket {b}");
        }
    }
    #[test] fn equal_keys_sparse_buckets_and_clears() {
        let mut h=FastHeap::new(); let mut model=BTreeMap::<(u64,u32),usize>::new();
        let mut rng=0xe34acbb768f12345u64;
        for step in 0..60_000u32 {
            rng^=rng<<13; rng^=rng>>7; rng^=rng<<17;
            if step%3901==0 {h.clear();model.clear();audit(&h);}
            if !model.is_empty() && (rng%3!=0 || h.count>1024) {
                assert_eq!(h.top(),Some(model.first_key_value().unwrap().0.0));
                let x=h.pop(); let k=model.get_mut(&x).unwrap(); *k-=1; if *k==0 {model.remove(&x);}
            } else {
                let delta=match rng%7 {0=>0,1=>1,2=>1<<7,3=>1<<15,4=>1<<23,5=>1<<31,_=>(rng>>24)&0xffff};
                let key=h.last+delta; let vertex=((rng>>32)%73) as u32;
                assert!(h.push(key,vertex)); *model.entry((key,vertex)).or_default()+=1;
            }
            assert_eq!(h.count,model.values().sum());
            if step%127==0 {audit(&h);assert_eq!(h.top(),model.first_key_value().map(|(x,_)|x.0));audit(&h);}
        }
        while !model.is_empty() {assert_eq!(h.top(),Some(model.first_key_value().unwrap().0.0));let x=h.pop();let k=model.get_mut(&x).unwrap();*k-=1;if *k==0{model.remove(&x);}}
        audit(&h);h.clear();audit(&h);
    }
}
