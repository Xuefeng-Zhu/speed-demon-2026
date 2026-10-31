#!/usr/bin/env python3
"""Emit test-only forced sparse/collision/worker/threshold-trace source."""
from pathlib import Path
import argparse
p=argparse.ArgumentParser();p.add_argument('--output',required=True);mode=p.add_mutually_exclusive_group();mode.add_argument('--force-sparse',action='store_true');mode.add_argument('--force-bitmap',action='store_true');p.add_argument('--zero-short-hash',action='store_true');p.add_argument('--workers',type=int);p.add_argument('--trace',action='store_true');a=p.parse_args();s=Path('experiments/b-sparse-rebased/threshold512.rs').read_text()
if a.force_sparse:
 x='if total <= 512 {';assert s.count(x)==1;s=s.replace(x,'if true {')
if a.force_bitmap:
 x='if total <= 512 {';assert s.count(x)==1;s=s.replace(x,'if false {')
if a.zero_short_hash:
 x='''    fn short_hash(mut x: u64) -> usize {
        x ^= x >> 30;
        x = x.wrapping_mul(0xbf58_476d_1ce4_e5b9);
        x ^= x >> 27;
        x = x.wrapping_mul(0x94d0_49bb_1331_11eb);
        ((x ^ (x >> 31)) >> 32) as usize
    }''';assert s.count(x)==1;s=s.replace(x,'    fn short_hash(_x: u64) -> usize { 0 }')
if a.workers:
 x='let nthreads = thread::available_parallelism().map_or(4, |n| n.get());';assert s.count(x)==1;s=s.replace(x,f'let nthreads = {a.workers};')
if a.trace:
 x='        if total <= 512 {';assert s.count(x)==1;s=s.replace(x,'        if qi < 9 { eprintln!("SPARSE_TRACE qi={qi} total={total} use_sparse={}",total <= 512); }\n'+x)
Path(a.output).write_text(s)
