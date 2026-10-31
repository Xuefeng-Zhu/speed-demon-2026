#!/usr/bin/env python3
"""Check balanced radix-heap ordering and occupancy against BinaryHeap.

The temporary test build uses the supplied candidate unchanged, appending a
Rust test module in the same compilation unit to access private heap fields.
It does not modify the source or require generated competition datasets.
"""
import argparse
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parent
TEST = r'''
#[cfg(test)]
mod independent_heap_checks {
    use super::*;
    use std::cmp::Reverse;
    use std::collections::BinaryHeap;

    #[test]
    fn occupancy_and_order_survive_interleaved_operations() {
        for seed in 1u64..=150 {
            let mut rng = seed;
            let mut h = RadixHeap::default();
            let mut q: BinaryHeap<Reverse<(u64, u32)>> = BinaryHeap::new();
            for step in 0..3000u32 {
                rng ^= rng << 13;
                rng ^= rng >> 7;
                rng ^= rng << 17;
                match rng % 31 {
                    0 => { h.clear(); q.clear(); }
                    1..=6 if !q.is_empty() => {
                        let key = h.top().unwrap();
                        assert_eq!(key, q.peek().unwrap().0.0);
                        let item = h.pop();
                        assert_eq!(item.0, key);
                        // Equal-key vertices may be popped in any order.
                        let mut all: Vec<_> = q.drain().map(|v| v.0).collect();
                        let pos = all.iter().position(|x| *x == item).unwrap();
                        all.swap_remove(pos);
                        q = all.into_iter().map(Reverse).collect();
                    }
                    7..=11 => assert_eq!(h.top(), q.peek().map(|v| v.0.0)),
                    _ => {
                        let delta = match rng % 7 {
                            0 => 0, 1 => 1, 2 => 255, 3 => 65535,
                            4 => u32::MAX as u64, _ => rng % 1000000,
                        };
                        let key = h.last.saturating_add(delta);
                        h.push(key, step);
                        q.push(Reverse((key, step)));
                    }
                }
                assert_eq!(h.count, q.len(), "seed={seed} step={step}");
                assert_eq!(h.count, h.buckets.iter().map(Vec::len).sum::<usize>());
            }
        }
    }
}
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=ROOT / 'meeting.rs')
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix='balanced-heap-check-') as directory:
        tmp = Path(directory)
        source = tmp / 'test.rs'
        binary = tmp / 'test'
        source.write_text(args.source.read_text() + TEST)
        subprocess.run(['rustc', '--edition=2021', '-C', 'opt-level=2',
                        '-C', 'overflow-checks=yes', '--test', str(source),
                        '-o', str(binary)], check=True)
        subprocess.run([str(binary)], check=True)


if __name__ == '__main__':
    main()
