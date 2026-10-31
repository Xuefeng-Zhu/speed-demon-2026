# Sort adjacency by weight (experimental, not selected)

This candidate sorts each node's packed outgoing edges by weight (then ID) while building each forward/backward CSR block, preserving all edges and their weights. The exact baseline is restored D `451429c`, source SHA-256 `1022f4d9c9956b17fd054e96a26d09551eff61936a851edf88505e12e2b1946c`. Sorting is runtime work included in timing; there is no precomputed input data.

Nine randomized shared ARM native pairs plus warmups all matched the official full seed-1 hash. Median wall was 0.27860 s candidate vs 0.26691 s baseline, CPU 1.86875 vs 1.83346 s, peak native process RSS 534,872,064 vs 535,986,176 B. All 16,000 independent random graph queries, 36,864 exhaustive small-graph queries, maximum-weight chain and 6,000 repeated/unreachable cases passed. Sorting added cost with no observed win on this screen; the candidate is not selected. This is neither x86 nor official cgroup data; no Mac Docker was used.
