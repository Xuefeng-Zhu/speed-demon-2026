#[cfg(test)]
mod batch_property {
    use super::*;
    use std::collections::HashSet;
    #[test]
    fn exact_snapshot_and_evictions() {
        // All slices live in the same immutable mapping, as in production.
        let mut buf = Vec::new();
        let mut spans = Vec::new();
        for i in 0..603usize {
            let name = if i == 0 { Vec::new() }
                else if i == 1 { vec![b'X'; 65_536] }
                else if i == 2 { b"A\"\"B".to_vec() }
                else { format!("Long common prefix {i:04} end").into_bytes() };
            if name.len() >= u16::MAX as usize {
                buf.push(b'"'); let at=buf.len(); buf.extend_from_slice(&name); buf.extend_from_slice(b"\",");
                spans.push((at as u32, u16::MAX));
            } else {
                let at=buf.len(); buf.extend_from_slice(&name);
                spans.push((at as u32, name.len() as u16));
            }
        }
        let recs: &'static [u8] = Box::leak(buf.into_boxed_slice());
        for groups in [1usize, 63, 64, 65, 240, 241, 256, 257, 513] {
            let words=groups.div_ceil(64);
            for mode in 0..3 {
                let mut events=Vec::new();
                let mut state=0x243f6a8885a308d3u64;
                // Interleave repeated fresh names, cache-slot A/B/A evictions,
                // full-hash promotions, long sentinels and group boundaries.
                for j in 0..24_003usize {
                    state ^= state << 13; state ^= state >> 7; state ^= state << 17;
                    let id = if j < 1206 { (j / 2) % spans.len() } else { state as usize % spans.len() };
                    let g = if j % 13 == 0 { groups - 1 } else { (state >> 23) as usize % groups };
                    let h=match mode { 0 => (id as u64) << 15, 1 => 0, _ => name_hash(event_name(recs,Event{offset:spans[id].0,len:spans[id].1,group:0,hash:0})) };
                    events.push(Event {offset:spans[id].0,len:spans[id].1,group:g as u16,hash:h});
                }
                let mut batched=OwnerDict::default();
                let mut scalar=OwnerDict::default();
                let mut got=vec![0i64;groups];
                let mut want=vec![0i64;groups];
                let mut oracle=HashSet::new();
                for chunk in events.chunks(4) {
                    batched.see_batch(recs,chunk,words,&mut got);
                    for &e in chunk {
                        let name=event_name(recs,e);
                        let g=e.group as usize;
                        let a=scalar.see(name,e.hash,g,words);
                        let b=oracle.insert((name,g)) as i64;
                        assert_eq!(a,b,"scalar/oracle groups={groups} mode={mode}");
                        want[g]+=b;
                    }
                    assert_eq!(got,want,"batch groups={groups} mode={mode}");
                }
            }
        }
    }
}
