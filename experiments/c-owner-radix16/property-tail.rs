#[cfg(test)]
mod radix_tests {
    use super::*;
    use std::collections::HashSet;
    #[test]
    fn stable_order_and_exact_group_counts() {
        let mut seed=0x123456789abcdef0u64;
        for len in [0usize,1,2,3,17,255,256,257,4097,65536] {
            let mut es=Vec::new();
            for i in 0..len {
                seed^=seed<<13; seed^=seed>>7; seed^=seed<<17;
                es.push(Event{offset:i as u32,len:(i%65000) as u16,group:(i%257) as u16,hash:seed});
            }
            let mut expected=es.clone(); expected.sort_by_key(|e|e.hash as u16);
            radix16(&mut es);
            assert_eq!(es.iter().map(|e|(e.offset,e.len,e.group,e.hash)).collect::<Vec<_>>(),expected.iter().map(|e|(e.offset,e.len,e.group,e.hash)).collect::<Vec<_>>());
        }
        let names:Vec<String>=(0..120).map(|i| if i==0 {String::new()} else {format!("Name{i:03}{}",if i%4==0{" "}else{""})}).collect();
        let mut raw=Vec::new();let mut offsets=Vec::new();
        for name in &names {offsets.push(raw.len() as u32);raw.extend_from_slice(name.as_bytes());raw.push(b',');}
        let recs: &'static [u8]=Box::leak(raw.into_boxed_slice());
        for groups in [1usize,63,64,65,241,257,513] {
            let mut events=Vec::new();let mut seen=HashSet::new();
            for i in 0..8000usize {
                seed^=seed<<13; seed^=seed>>7; seed^=seed<<17;
                let name=(seed as usize)%names.len();
                seed^=seed<<13; seed^=seed>>7; seed^=seed<<17;
                let group=(seed as usize)%groups;
                // Many distinct names deliberately share the same low-16 key.
                let hash=(name%3) as u64 | ((name as u64)<<32);
                events.push(Event{offset:offsets[name],len:names[name].len() as u16,group:group as u16,hash});
                seen.insert((name,group));
            }
            radix16(&mut events);let mut counts=vec![0i64;groups];
            reduce_sorted(recs,&events,groups.div_ceil(64),&mut counts);
            let mut expected=vec![0i64;groups];for (_,g) in seen {expected[g]+=1;}
            assert_eq!(counts,expected,"groups={groups}");
        }
    }
}
