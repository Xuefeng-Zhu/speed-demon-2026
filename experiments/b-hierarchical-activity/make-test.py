#!/usr/bin/env python3
"""Test-only controls for bitmap cap and evidence of sparse dense-operation branch."""
import argparse
from pathlib import Path
p = argparse.ArgumentParser()
p.add_argument('--source', required=True)
p.add_argument('--output', required=True)
p.add_argument('--zero-cache', action='store_true')
p.add_argument('--trace', action='store_true')
a = p.parse_args()
s = Path(a.source).read_text()
if a.zero_cache:
    old = 'DenseCache::new(plan.keys.len(), 64 * 1024 * 1024)'
    assert s.count(old) == 1
    s = s.replace(old, 'DenseCache::new(plan.keys.len(), 0)')
if a.trace:
    old = "if (op == b'A' || op == b'N') && (active_count as usize) * 2 < words {"
    assert s.count(old) == 1
    extra = '''
                        static ONCE: std::sync::atomic::AtomicBool = std::sync::atomic::AtomicBool::new(false);
                        if !ONCE.swap(true, std::sync::atomic::Ordering::Relaxed) { eprintln!("SPARSE_DENSE_BRANCH_REACHED"); }'''
    s = s.replace(old, old + extra)
Path(a.output).write_text(s)
