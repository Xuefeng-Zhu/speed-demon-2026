#!/usr/bin/env python3
"""Check balanced radix-heap occupancy and ordering under randomized operations."""
from pathlib import Path
import subprocess
import tempfile

HERE = Path(__file__).resolve().parent
TEST = '\n#[cfg(test)]\nmod independent_heap_test {\n    use super::RadixHeap;\n    use std::collections::BTreeMap;\n    fn random(state: &mut u64) -> u64 { *state ^= *state << 13; *state ^= *state >> 7; *state ^= *state << 17; *state }\n    fn verify(h: &RadixHeap, reference: &BTreeMap<u64, Vec<u32>>) {\n        let actual: usize = h.buckets.iter().map(Vec::len).sum();\n        let expected: usize = reference.values().map(Vec::len).sum();\n        assert_eq!(h.count, actual); assert_eq!(h.count, expected);\n        for (i, bucket) in h.buckets.iter().enumerate() { for &(k, _) in bucket { assert!(k >= h.last); assert_eq!(h.slot(k), i); } }\n    }\n    #[test]\n    fn randomized_multiheap_peek_pop_clear() {\n        let mut heaps: [RadixHeap; 2] = Default::default();\n        let mut refs: [BTreeMap<u64, Vec<u32>>; 2] = Default::default();\n        let mut state = 0x98ae77123579bdf1u64;\n        for step in 0..150_000u32 {\n            let side = (random(&mut state) & 1) as usize;\n            let action = random(&mut state) % 100;\n            let h = &mut heaps[side]; let r = &mut refs[side];\n            if action < 50 || r.is_empty() {\n                let delta = match random(&mut state) % 10 {0 => 0, 1 => u64::MAX, 2 => 1u64 << 32, _ => random(&mut state) % 10000};\n                let k = h.last.saturating_add(delta); h.push(k, step); r.entry(k).or_default().push(step);\n            } else if action < 70 {\n                assert_eq!(h.top(), r.first_key_value().map(|(&k,_)| k));\n            } else if action < 97 {\n                let min = *r.first_key_value().unwrap().0;\n                assert_eq!(h.top(), Some(min)); let (k,v) = h.pop(); assert_eq!(k,min);\n                let values = r.get_mut(&k).unwrap(); let ix=values.iter().position(|&x|x==v).unwrap(); values.swap_remove(ix); if values.is_empty(){ r.remove(&k); }\n            } else { h.clear(); r.clear(); }\n            verify(h,r);\n        }\n    }\n}\n'

with tempfile.TemporaryDirectory(prefix="sd-heap-invariant-") as tmp:
    root = Path(tmp)
    source = root / "combined.rs"
    binary = root / "heap-test"
    source.write_text((HERE / "meeting.rs").read_text() + TEST)
    subprocess.run(["rustc", "--test", "--edition=2021", "-C", "opt-level=1",
                    "-C", "overflow-checks=yes", str(source), "-o", str(binary)], check=True)
    subprocess.run([str(binary), "--nocapture"], check=True)
