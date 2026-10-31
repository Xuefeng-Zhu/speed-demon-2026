# D coarse radix keys on the round-3 source

`baseline.rs` is `track-d/src/main.rs` at `dddc0ea` (round-3 renumbered source). The candidate, now in `track-d/src/main.rs`, makes one change: both search queues are keyed by `distance >> 6` (`SHIFT`) instead of the exact distance. Exact distances are still stored and relaxed. A popped node is skipped only if its current distance falls in an earlier bucket, so it was already expanded with that distance; otherwise it is expanded with its current distance, even if it was expanded before. The stop test uses the bucket starts, `(a + b) << 6 >= best`, as lower bounds. This is the coarse-bucket idea from `../track-d-coarse-buckets24/` (board 0.345 → 0.313–0.321 s on the older source), which the speed-opt rewrite had dropped.

Correctness argument: on each side, every improvement is queued in the current bucket or a later one, because weights are non-negative, and is expanded with its new distance. Suppose a path shorter than `best` existed. Take its first node on the forward side that has not been expanded with its exact distance: that node is still queued at a key of at least the forward bucket start. Likewise on the backward side. If the two nodes overlap, some node has exact labels on both sides, and the meeting check run when the later label was set already found the path. Otherwise the path length is at least the sum of the two bucket starts, which is at least `best`. The u32 cutoff and the exact u64 rerun are unchanged.

## Checks (sandbox, 8-core Linux VM, October 31 2026)

- Full seed 1: output SHA-256 `a23dbdf0…277e` matched on every run.
- An overflow- and debug-checked build passed `track-d-balanced-frontier/oracle.py` (16,000 random queries), `exhaustive.py` (36,864 queries), `track-d-u32-fallback/thresholds.py`, `track-d-packed32-adj/boundaries.py` (2^21 and 2^21+1 nodes) and `track-d-balanced-frontier/extremes.py`.
- `same_bucket.py` checks 40 dense graphs with mostly-sub-64 weights, zero cycles and parallel edges against Python Dijkstra (46,336 all-pairs answers). Both candidate and baseline passed. An instrumented copy counted 3,270,774 repeat expansions and 1,977 stale skips, so both paths ran.

## Timing (sandbox, not the scoring box)

`bench.py`-style alternating runs on full seed 1, wall time including process start:

| Binary | Runs | Median | Min |
|---|---:|---:|---:|
| baseline | 21 | 199.1 ms | 194.2 ms |
| SHIFT 6 | 21 | 183.5 ms | 176.5 ms |

A shorter 11-run width screen: SHIFT 4 183.5, 5 181.4, 6 180.7, 7 179.9, 8 185.4 ms median. Widths 5–7 are within noise of each other; 6 was kept. Only the board can confirm the gain on the scoring machine.
