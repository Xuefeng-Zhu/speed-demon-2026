#[cfg(test)]
mod property {
    use super::*;
    use std::collections::{BTreeMap, HashSet};
    fn rng(s:&mut u64)->u64 { *s ^= *s << 13; *s ^= *s >> 7; *s ^= *s << 17; *s }
    #[test] fn monotone_mixed() {
        let mut rngstate=0x4f91d185c27a9661u64;
        let mut heap=RadixHeap::default();
        let mut refmap:BTreeMap<u64,HashSet<u32>>=BTreeMap::new();
        let mut next=0u32; let mut live=0usize;
        for epoch in 0..40 {
            for step in 0..25000 {
                let r=rng(&mut rngstate);
                if refmap.is_empty() || r % 100 < 65 {
                    let shift=(rng(&mut rngstate)%64) as u32;
                    let delta=if r&7==0 {0} else {rng(&mut rngstate) & (u64::MAX >> shift)};
                    let k=heap.last.saturating_add(delta);
                    next=next.checked_add(1).unwrap();
                    heap.push(k,next); live+=1; assert!(refmap.entry(k).or_default().insert(next));
                } else {
                    let expected=*refmap.keys().next().unwrap();
                    assert_eq!(heap.top(),Some(expected)); assert_eq!(heap.top(),Some(expected));
                    let (k,v)=heap.pop(); live-=1; assert_eq!(k,expected);
                    let entries=refmap.get_mut(&k).unwrap(); assert!(entries.remove(&v));
                    if entries.is_empty(){refmap.remove(&k);}
                }
                assert_eq!(heap.count,live,"epoch {epoch} step {step}");
            }
            while !refmap.is_empty() {
                let expected=*refmap.keys().next().unwrap(); assert_eq!(heap.top(),Some(expected));
                let (k,v)=heap.pop(); live-=1; assert_eq!(k,expected);let entries=refmap.get_mut(&k).unwrap();
                assert!(entries.remove(&v));if entries.is_empty(){refmap.remove(&k);}
            }
            assert_eq!(heap.top(),None);assert_eq!(live,0);heap.clear(); assert_eq!(heap.last,0); assert_eq!(heap.count,0);
        }
    }
}
