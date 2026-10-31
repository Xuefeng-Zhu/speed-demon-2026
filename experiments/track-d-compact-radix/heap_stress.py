#!/usr/bin/env python3
"""Independently model-check the compact priority queue with runtime-only inputs."""
from pathlib import Path
import subprocess
import tempfile

source = Path(__file__).with_name('meeting.rs').read_text()
tests = r'''
#[cfg(test)]
mod independent_heap_check {
    use super::*;
    use std::collections::BTreeMap;
    const CUT: u64 = 1u64 << 43;
    fn random(x: &mut u64) -> u64 {
        *x ^= *x << 13; *x ^= *x >> 7; *x ^= *x << 17; *x
    }
    fn add(h: &mut RadixHeap, m: &mut BTreeMap<(u64,u32), usize>, k: u64, v: u32) {
        h.push(k, v); *m.entry((k,v)).or_default() += 1;
    }
    #[test]
    fn monotone_operations_and_clears() {
        let mut seed = 0x19ab_34cd_9876_5432u64;
        let mut h = RadixHeap::default();
        let mut m = BTreeMap::<(u64,u32), usize>::new();
        for round in 0..150 {
            assert_eq!(h.count, 0);
            assert_eq!(h.top(), None);
            let keys = match round % 3 {
                0 => [0, 0, CUT-1, CUT, CUT, CUT+1, (1<<53)-1],
                1 => [CUT-2, CUT-1, CUT-1, CUT, CUT, CUT+1, (1<<53)-1],
                _ => [CUT, CUT, CUT+1, CUT+2, CUT+3, CUT+4, (1<<53)-1],
            };
            for (i, k) in keys.iter().enumerate() {
                add(&mut h, &mut m, *k, if i % 2 == 0 { (1<<21)-1 } else { 0 });
            }
            for step in 0..3000 {
                let (&(smallest, _), _) = m.first_key_value().unwrap();
                assert_eq!(h.top(), Some(smallest));
                assert_eq!(h.top(), Some(smallest));
                let (k,v) = h.pop();
                assert_eq!(k, smallest);
                let cnt = m.get_mut(&(k,v)).expect("popped non-member");
                *cnt -= 1;
                if *cnt == 0 { m.remove(&(k,v)); }
                assert_eq!(h.count, m.values().sum());
                let pushes = match random(&mut seed) % 7 { 0 => 0, 1 => 3, _ => 1 };
                for _ in 0..pushes {
                    let delta = match random(&mut seed) % 7 {
                        0 => 0, 1 => 1, 2 if k < CUT => CUT-k,
                        3 if k < CUT-1 => CUT-1-k,
                        _ => random(&mut seed) % 65536,
                    };
                    let key = k.saturating_add(delta);
                    let id = match random(&mut seed) % 3 {
                        0 => 0, 1 => (1<<21)-1,
                        _ => (random(&mut seed) % (1<<21)) as u32,
                    };
                    add(&mut h, &mut m, key, id);
                }
                if m.is_empty() { add(&mut h, &mut m, k, 0); }
                if step % 173 == 0 { assert_eq!(h.small_count + h.wide.count, h.count); }
            }
            // Clear while both heaps may be populated and re-enter with smaller keys.
            h.clear(); m.clear();
            assert_eq!(h.count, 0);
            assert_eq!(h.small_count, 0);
            assert_eq!(h.wide.count, 0);
            assert_eq!(h.top(), None, "round {round}");
        }
    }
}
'''
with tempfile.TemporaryDirectory(prefix='d-radix-independent-') as tmp:
    path = Path(tmp)
    (path/'check.rs').write_text(source + tests)
    subprocess.run(['rustc', '--edition=2021', '--test', '-C', 'opt-level=2', '-C', 'overflow-checks=on', str(path/'check.rs'), '-o', str(path/'check')], check=True)
    subprocess.run([str(path/'check'), '--nocapture'], check=True)
