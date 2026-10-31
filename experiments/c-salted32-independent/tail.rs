#[cfg(test)]
mod independent_event_oracle {
    use super::*;
    use std::collections::HashSet;

    #[test]
    fn routed_events_match_full_exact_set_under_adversarial_collisions() {
        assert_eq!(std::mem::size_of::<Event>(), 12);
        // Exact encoded bytes including escaped quotes and significant trailing spaces.
        let mut names: Vec<Vec<u8>> = (0..1024).map(|i| {
            format!("Name{:04}{}{}", i, if i % 5 == 0 { " \"\"Q\"\"" } else { "" }, " ".repeat(i % 7)).into_bytes()
        }).collect();
        names.push(Vec::new());
        names.push(vec![b'X'; 65535]);
        names.push(vec![b'Y'; 65536]);
        let mut recs = Vec::new(); let mut starts = Vec::new();
        for name in &names {
            recs.push(b'"'); starts.push(recs.len()); recs.extend_from_slice(name); recs.extend_from_slice(b"\",");
        }
        let recs: &'static [u8] = Box::leak(recs.into_boxed_slice());
        for &parts in &[1usize, 3, 12] {
            for mode in 0..4 {
                let mut dicts: Vec<OwnerDict> = (0..parts).map(|_| OwnerDict::default()).collect();
                let mut oracle: HashSet<(Vec<u8>, usize)> = HashSet::new();
                for step in 0..160_000usize {
                    let idx = if step < names.len() { step } else { step.wrapping_mul(0x9e3779b9).rotate_left(11) % names.len() };
                    let group = (step.wrapping_mul(73) ^ (step >> 5)) % 257;
                    let h = match mode {
                        0 => name_hash(&names[idx]),
                        // Synthetic full hashes make all low32 equal, spread owners, or both.
                        1 => 0x1234_5678_9abc_def0,
                        2 => ((idx as u64).wrapping_mul(0x9e3779b9) << 32) | 0x9abc_def0,
                        _ => 0x2000_0000_0000_0000 | (((idx / 12) as u64) << 15),
                    };
                    let owner = ((h as u128 * parts as u128) >> 64) as usize;
                    let event = Event { offset: starts[idx] as u32, len: u16::try_from(names[idx].len()).unwrap_or(u16::MAX), group: group as u16, hash: h as u32 };
                    let restored = event_name(recs, event);
                    assert_eq!(restored, names[idx]);
                    let expected = oracle.insert((names[idx].clone(), group));
                    let got = dicts[owner].see(restored, event.hash as u64, event.group as usize, 5);
                    assert_eq!(got, i64::from(expected), "parts={parts} mode={mode} step={step}");
                }
                assert_eq!(dicts.iter().map(|d| d.entries.len()).sum::<usize>(), names.len());
            }
        }
    }
}
