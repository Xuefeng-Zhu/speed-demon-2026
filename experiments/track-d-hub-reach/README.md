# Track D hub reachability precheck (not selected)

This isolated experiment computes reachability from and to node 0 at runtime,
using two concurrent breadth-first traversals. If the hub reaches a source but
not its target, or the target reaches the hub but its source does not, then
the queried path cannot exist. All other queries use the selected exact
bidirectional Dijkstra. `baseline.rs` SHA-256 is
`1022f4d9c9956b17fd054e96a26d09551eff61936a851edf88505e12e2b1946c`.
This is not independently reviewed or promoted.

All full seed-1 hashes matched in seven alternating measured pairs and a
warmup. Native shared ARM median wall was 0.34304 s versus baseline 0.27022 s;
median CPU 1.97937 versus 1.83145 s, and maximum process RSS 536,805,376
versus 535,740,416 bytes. This is not an official x86 or cgroup result.
Independent tests passed 16,000 random directed-graph Dijkstra-oracle queries
and 36,864 exhaustive all-pairs queries across 4,096 three-node graphs.
One instrumented full-data profile found only 10 of 2,000 queries eliminated;
node 0 reached 1,740,366 of 1,740,512 nodes and was reachable from 1,740,366.
The preprocessing cost dominated in this dataset. Input data is not included.
