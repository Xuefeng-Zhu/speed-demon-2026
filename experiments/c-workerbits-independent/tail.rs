#[cfg(test)]
mod independent_workerbits {
    use super::*;
    use std::sync::{Barrier, atomic::{AtomicPtr,Ordering}};
    #[test]
    fn synchronized_claims_fallback_and_group_boundaries() {
        let mut long=vec![b'Q';65537]; long.extend_from_slice(b"\"\"tail");
        let names:Vec<&'static [u8]> = [b"".as_slice(), b"A", b"A ", b"A\"\"B", b"B", &long]
            .iter().map(|s| &*Box::leak(s.to_vec().into_boxed_slice())).collect();
        let groups = [0usize,1,62,63,64,65,126,127,128,129,190,191,192,193,254,255];
        for n in [1usize,2,7,16] { for forced_winner in [None,Some(0usize),Some(3),Some(5)] {
            let slots=[AtomicPtr::<DirectNode>::new(std::ptr::null_mut())];
            let fallback:Vec<DirectShard>=(0..1024).map(|_|DirectShard::default()).collect();
            if let Some(i)=forced_winner { assert_eq!(direct_see(&slots,&fallback,names[i],0,4,0,0,n),0); }
            let barrier=Barrier::new(n);
            let contributions=thread::scope(|sc| {
                let mut hs=Vec::new();
                let (slots,fallback,names,groups,barrier)=(&slots,&fallback,&names,&groups,&barrier);
                for t in 0..n { hs.push(sc.spawn(move || {
                    let mut counts=[0i64;256]; barrier.wait();
                    // Vary worker order so winner and collisions are contested.
                    for round in 0..3 { for j in 0..names.len() {
                        let name=names[(j+t+round)%names.len()];
                        for &g in groups { counts[g]+=direct_see(slots,fallback,name,g,4,0,t,n); }
                    }}
                    counts
                })); }
                hs.into_iter().map(|h|h.join().unwrap()).collect::<Vec<_>>()
            });
            let node=unsafe { &*slots[0].load(Ordering::Acquire) };
            if let Some(i)=forced_winner { assert_eq!(node.name,names[i]); }
            let mut total=[0i64;256];
            for c in contributions {for (sum,v) in total.iter_mut().zip(c) {*sum+=v;} }
            for g in 0..256 { let mut bits=0;
                for t in 0..n { bits |= unsafe {*node.bits[t*4+g/64].get()}; }
                total[g] += ((bits>>(g%64)) & 1) as i64;
                assert_eq!(total[g], if groups.contains(&g) { names.len() as i64 } else {0}, "n={n} forced={forced_winner:?} g={g}");
            }
            // Nodes are retained through all accesses; now reclaim only in the test.
            unsafe {drop(Box::from_raw(slots[0].load(Ordering::Acquire)));}
        }}
    }
}
