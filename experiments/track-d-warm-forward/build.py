#!/usr/bin/env python3
"""Produce isolated bounded forward-warmup variants from their frozen baseline."""
from pathlib import Path

root = Path(__file__).resolve().parent
base = (root / "baseline.rs").read_text()
old = '''        self.reach(0, s, 0);
        self.reach(1, t, 0);
        let mut best = NONE;
'''
assert base.count(old) == 1
for count in (1, 2, 4, 8, 16):
    new = '''        self.reach(0, s, 0);
        let mut best = NONE;
        // Exact bounded forward Dijkstra warmup; preserve all distances and
        // the remaining heap for the ordinary bidirectional continuation.
        for _ in 0..WARMUP {
            if self.heaps[0].top().is_none() { break; }
            let (d, u) = self.heaps[0].pop();
            if d > !self.dist[u as usize][0] { continue; }
            if u == t { best = d; break; }
            for (v, w) in graphs[0].edges(u) {
                self.reach(0, v, d + w);
            }
        }
        let target_forward = self.dist[t as usize][0];
        if target_forward != 0 { best = best.min(!target_forward); }
        self.reach(1, t, 0);
'''.replace('WARMUP', str(count))
    (root / f"warm{count}.rs").write_text(base.replace(old, new))
