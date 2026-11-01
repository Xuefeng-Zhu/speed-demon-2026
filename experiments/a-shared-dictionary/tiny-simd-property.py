#!/usr/bin/env python3
"""Emit a standalone property program containing the candidate's exact SIMD kernel.

This helper generates source only. On native x86, compile the emitted Rust with
--edition 2021 -O -C target-cpu=x86-64-v3 -C overflow-checks=yes, then run it.
"""

import argparse
import hashlib
from pathlib import Path

TAIL = r"""
fn check(values: &[u32], at: usize, padding: u32) {
    let n = values.len();
    let mut lat = vec![padding; at + 8];
    lat[at..at + n].copy_from_slice(values);
    let mut sorted = values.to_vec();
    sorted.sort_unstable();
    for rank in 0..n {
        let ranks = [rank, (rank + 1) % n, (rank + n - 1) % n];
        assert_eq!(small_ranks(&lat, at, n, ranks), ranks.map(|r| sorted[r]),
                   "values={values:?} at={at} padding={padding} ranks={ranks:?}");
    }
    let ranks = [50, 95, 99].map(|p| (p * n + 99) / 100 - 1);
    assert_eq!(small_ranks(&lat, at, n, ranks), ranks.map(|r| sorted[r]));
}

fn main() {
    let alphabet = [0, 1, 1 << 31, u32::MAX];
    let boundary = [0, 1, 65535, (1 << 31) - 1, 1 << 31,
                    (1 << 31) + 1, u32::MAX - 1, u32::MAX];
    let mut cases = 0usize;
    let mut state = 0x62ab_d931_76ed_3015u64;
    for n in 1..=8usize {
        // Exhaust ties, zero, unsigned-order crossing, and genuine u32::MAX values.
        for code in 0..1usize << (2 * n) {
            let mut digits = code;
            let values: Vec<u32> = (0..n).map(|_| {
                let value = alphabet[digits & 3];
                digits >>= 2;
                value
            }).collect();
            check(&values, code & 7, if code & 8 == 0 { 0 } else { u32::MAX });
            cases += 1;
        }
        // Exercise each alignment, nonzero offset and ignored-tail pattern explicitly.
        for at in 0..8 {
            for &padding in &boundary {
                for rotation in 0..8 {
                    let values: Vec<u32> = (0..n).map(|i| boundary[(i + rotation) & 7]).collect();
                    check(&values, at, padding);
                    cases += 1;
                }
            }
        }
        for number in 0..10_000usize {
            let values: Vec<u32> = (0..n).map(|i| {
                state ^= state << 13;
                state ^= state >> 7;
                state ^= state << 17;
                if number % 3 == 0 { boundary[((state as usize & 7) + i) & 7] }
                else { state as u32 }
            }).collect();
            check(&values, number & 7, boundary[number & 7]);
            cases += 1;
        }
    }
    println!("tiny SIMD exact-kernel properties passed: {cases} cases");
}
"""


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path,
                        default=Path(__file__).with_name("tiny-simd.rs"))
    parser.add_argument("--emit", type=Path, required=True)
    args = parser.parse_args()
    source = args.source.read_text()
    marker = "fn small_ranks("
    if source.count(marker) != 1:
        parser.error("expected exactly one non-generic small_ranks function")
    start = source.index(marker)
    end = source.index("{", start) + 1
    depth = 1
    while depth:
        if source[end] == "{":
            depth += 1
        elif source[end] == "}":
            depth -= 1
        end += 1
    kernel = source[start:end]
    args.emit.write_text(kernel + "\n" + TAIL)
    print(f"Emitted {args.emit}; kernel SHA-256 {hashlib.sha256(kernel.encode()).hexdigest()}")


if __name__ == "__main__":
    main()
