# D coarse-bucket radix experiment — unselected

Baseline is the exact selected batch16 source SHA-256 `7fd333be25133a78264cb4b84441de46d4c8bcbfd73914af23761f23d8c47f17`; candidate is `2a2a325a1c87e4bc68c260e0d80353e0b8f1f9a7b5be81b1ffeaaede6d813f9d`. The candidate changes only narrow FastHeap ordering: the existing duplicate-entry radix heap is keyed by quotient `d >> 6`, but stores and relaxes the exact distance `d`. Its top returns the bucket start (a conservative lower bound); each successful strict decrease is queued, including decreases after a vertex has already been expanded, and stale entries are skipped. The existing 65,536-entry per-heap fixed pool, cleanup, narrow cutoff and exact indexed-wide fallback are unchanged. Bounds are checked only between complete vertex expansions, at most 16 pops at a time. A coarser order can expand more nodes or trigger fallback more often; no claim of worst-case speed or hidden-data 8 GiB parent-cgroup safety is made.

Independent review supplied this correctness argument under nonnegative directed weights: for each side, every vertex with true distance below its minimum pending bucket start has been expanded at that exact distance; otherwise the first nonfinal vertex on a shortest path would already have a pending exact decrease below that bound. A path shorter than the sum of the two bucket starts must have an intersection already discovered at exact cost by both sides, and hence cannot improve the best recorded meeting. Quotients never decrease along relaxations; duplicate and stale queue entries are conservative. Empty frontier is considered only between full expansions. Review found no concrete defect; this reasoning does not substitute for independent tests.

## Evidence and limitations

Both exact sources were compiled natively with Rust opt-level 3, fat LTO and one codegen unit. Two serialized full public-seed ARM comparisons measured candidate/baseline median wall `0.225109/0.248193 s` (11 paired runs) and `0.227067/0.249066 s` (15 paired runs), approximately 9.3% and 8.8% faster. CPU medians were 1.594133/1.773000 and 1.588650/1.778086 s. Every one of the 56 warmup and timed runs matched the published output SHA-256 `a23dbdf0a3e49cc8901310a9ee1dc6a9a569a85297b6da75c2a7002cb2ed277e`. Raw reports are provided. Shared ARM performance and native process RSS are not x86 or official parent-cgroup results.

`verify.py` passed overflow/debug-asserted builds with capacities 0, 1, 2, 15, 16, 17, and 65,536: 16,000 random oracle queries and 36,864 exhaustive directed graph queries per cap, cutoff boundary checks, packed and wide CSR boundaries (`2^21`, `2^21+1` nodes), a maximum-weight chain, and 6,000 repeated/unreachable queries. `adversarial.py` passed ten dense directed graphs with zero-weight cycles, parallel edges, and all 23,040 pairs per cap at 2, 16, and 65,536. An instrumented default-cap run recorded 4,738,464 repeat expansions and 1,039,433 descending exact-key pops, showing the non-Dijkstra order and reconsideration path were exercised. `long_bucket.py` passed an 8,191-node same-bucket zero-cycle graph and directly observed capacity-2 and capacity-16 exhaustion followed by correct exact fallback. Packaged `verify.py` and `adversarial.py` were rerun after copying; long-bucket was tested on byte-identical source and script before copying. These checks and independent review do not establish exhaustive correctness or an official memory bound.

## Serialized dot VM comparison

No datasets, credentials, or binaries are included. On x86 with a separately generated official full seed-1 D dataset and no competing benchmark, run from this directory:

```sh
python3 verify.py
python3 adversarial.py
python3 long_bucket.py
python3 compare.py --data /path/to/full-d --build-dir /tmp/d-coarse24-first --report /tmp/d-coarse24-first.json --runs 15 --seed 82417
python3 compare.py --data /path/to/full-d --build-dir /tmp/d-coarse24-repeat --report /tmp/d-coarse24-repeat.json --runs 15 --seed 745831
```

The comparator checks every output against the official seed-1 hash and records wall, CPU and native process RSS; it does not measure parent-cgroup peak. Check 8 GiB behavior separately if feasible; VM RSS is not proof for hidden data. Target official build and practice require their own review. Do not run Docker on the Mac, prune images, change system limits, or use unrelated data.

Parent-run dot VM paired full-seed x86 tests showed 5.9% and 8.4% lower wall and 8.9% and 9.4% lower CPU in two 17-pair batches. All 72 full hashes, seven forced-capacity variants, randomized/exhaustive/extreme cases, zero cycles and actual pool-exhaustion fallback passed. Native RSS is not official parent-cgroup memory and cannot establish the 8 GiB hidden-data bound. The candidate is sent for reversible official practice.
