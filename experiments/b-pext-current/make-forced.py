#!/usr/bin/env python3
from pathlib import Path
import sys
s=Path('experiments/b-pext-current/candidate.rs').read_text()
a='''    fn short_hash(mut x: u64) -> usize {
        x ^= x >> 30;
        x = x.wrapping_mul(0xbf58_476d_1ce4_e5b9);
        x ^= x >> 27;
        x = x.wrapping_mul(0x94d0_49bb_1331_11eb);
        ((x ^ (x >> 31)) >> 32) as usize
    }'''
assert s.count(a)==1
Path(sys.argv[1]).write_text(s.replace(a,'    fn short_hash(_x: u64) -> usize { 0 }'))
