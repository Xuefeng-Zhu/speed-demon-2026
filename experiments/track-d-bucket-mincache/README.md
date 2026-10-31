# Cached radix bucket minima (experimental, not selected)

The candidate maintains the exact minimum of each nonzero radix bucket when pushing, replacing the redistribution scan with a cached value. Baseline is exact restored D source at `451429c`. All full hashes, 16,000 independent random graph queries, 36,864 exhaustive queries, maximum-weight chain and 6,000 repeated/unreachable queries passed.

Nine randomized shared ARM native pairs (`report.json`) gave median 0.28714 s candidate vs 0.27568 s baseline, CPU 1.88711 vs 1.83599 s, and peak native process RSS 534,118,400 vs 535,232,512 B. This screen showed no win; candidate remains unselected. It is not an official x86/cgroup result. No Mac Docker was used.
