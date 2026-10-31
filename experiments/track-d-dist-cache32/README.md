# Compact distance reject cache (experimental, not selected)

This prototype uses a 1,024-entry per-worker cache of 32-bit `(node+side, tentative-distance)` values cleared before each nontrivial query. Distances beyond u32 range bypass it; node IDs are below 2^21 by the official spec. A previous tentative distance is an upper bound on current best within a query, so rejecting only if the cached distance is no larger than the proposed distance is safe; tag conflicts fall back to the authoritative dense pair. Baseline is mapped-input D at `a9e1d0d`.

It passed all full hashes, 16,000 independent random graph queries, 36,864 exhaustive small-graph queries, the maximum-size maximum-weight chain and 6,000 repeated/unreachable queries. Nine shared ARM native pairs (`report.json`) measured median 0.39158 vs 0.31061 s baseline, CPU 2.09446 vs 1.85454 s, maximum native RSS 548,487,168 vs 548,864,000 B. The candidate is slower in this screen and remains unselected; this is neither target x86 nor official cgroup evidence. No Mac Docker was used.

One separate instrumented full-seed ARM run (`profile.rs`, `profile.txt`) counted 3,478,760 cached rejections among 20,976,116 reach attempts (16.6%); the output hash matched. Instrumentation changes execution and this count is not a target timing. Despite those hits, the paired screen above was slower.
