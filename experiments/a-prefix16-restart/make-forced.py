#!/usr/bin/env python3
"""Write temporary test-only weak-hash collision and/or restart trace source."""
import argparse
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--zero-weak',action='store_true');p.add_argument('--trace',action='store_true');a=p.parse_args();s=a.source.read_text()
if a.zero_weak:
 old='if WEAK { h ^= ((e - s) as u64).wrapping_mul(MIX); }';assert s.count(old)==1;s=s.replace(old,'if WEAK { h = 0; }')
if a.trace:
 old='parse_impl::<true>(d, i, end).unwrap_or_else(|| parse_impl::<false>(d, i, end).unwrap())';new='parse_impl::<true>(d, i, end).unwrap_or_else(|| { eprintln!("WEAK_RESTART"); parse_impl::<false>(d, i, end).unwrap() })';assert s.count(old)==1;s=s.replace(old,new)
a.output.write_text(s)
