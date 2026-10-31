# Track D non-branching path expansion (not selected)

This isolated experiment eagerly follows vertices with out-degree one in the
active direction, without placing them in the priority queue. It still records
their distances and opposite-side meetings; it enqueues branching vertices,
and stops on dead ends or non-improving distances, including zero-weight cycles.
It makes no assumption about vertex IDs, edge weights or cached answers.
The selected baseline SHA-256 is
`1022f4d9c9956b17fd054e96a26d09551eff61936a851edf88505e12e2b1946c`.

All full seed-1 hashes matched in seven alternating measured pairs and a
warmup. Shared native ARM median wall was 0.27253 s versus 0.27221 s baseline,
and median CPU 1.82036 versus 1.85636 s; maximum process RSS was 533,938,176
versus 535,035,904 bytes. Individual runs were noisy. The candidate passed
16,000 random directed-graph Dijkstra-oracle queries and 36,864 exhaustive
three-node all-pairs checks in an overflow-checked build. Measurements are
not official x86 or cgroup scores. Because the wall result is tied and the
algorithm is more complex, this is not promoted or independently reviewed.
No datasets are included.
