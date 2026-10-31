# Two-query interleaved D search (unselected)

`baseline.rs` is exact selected packed-adjacency D source SHA-256 `793d13729fe4dabe2a1ed272fef78e19567456676ed8df52c075bc4ac33ebd05`; `candidate.rs` is SHA-256 `cd1d2f7445c32360ec1abb05ff00c1d718a1d534ebf4aad012d5a932c514b530`. This experimental variant batches queries in input-order pairs and gives each worker two independent `Search` states. For each search it prepares the same next heap pop, prefetches the popped node's distance and CSR row on x86-64 or AArch64, lets the other search prepare, and expands the first before its next preparation. Each state retains the original per-side priority ordering and stopping rule; results are stored in original input order. Self-queries, absent second queries and cleared state are handled independently. The target prefetch branch is not exercised by native ARM timing.

A debug-assertion/overflow-checked ARM build passed 80 random directed graphs / 16,000 independent Dijkstra queries, all 4,096 three-node graphs / 36,864 Floyd–Warshall answers, 288 independently generated batches with empty and odd query counts, the 2^21/2^21+1 packed/fallback boundaries, the maximum-size maximum-weight chain and 6,000 repeated/unreachable queries. An independent static reviewer found no concrete ordering, stale-pop, odd-query, self-query, pointer or overflow defect; this is not exhaustive concurrency or target correctness evidence. Two per-worker search states increase memory and dynamic radix queues have no proven 8 GiB cgroup bound.

On the shared native ARM Mac, 15 randomized measured sample pairs after one warmup had candidate median wall **0.026644 s** vs baseline **0.022861 s** (+16.5%), median CPU 0.126625 vs 0.108758 s, and maximum process RSS 80,773,120 vs 56,475,648 bytes. All 32 sample hashes matched `a4c76ed030bc7e365db33191f6cf74708fba7f25eb48d64c8c4279f2e57046a0`. Raw per-run observations and source hashes are in `sample-arm.json`. An initial comparator run stopped immediately after its baseline warmup because of a harness name typo; it was fixed before the recorded comparison. Short sample timings and shared-host activity limit inference; no full-data, x86 or official cgroup result is claimed. Given the slower observed wall/CPU and higher memory, the candidate remains unselected.

Reproduce with the public generated sample and hash above:

```
rustc --edition=2021 -O -C overflow-checks=yes -C debug-assertions=yes experiments/track-d-interleaved2/candidate.rs -o /tmp/sd-d-interleaved2-debug
python3 experiments/track-d-balanced-frontier/oracle.py /tmp/sd-d-interleaved2-debug
python3 experiments/track-d-balanced-frontier/exhaustive.py /tmp/sd-d-interleaved2-debug
python3 experiments/track-d-interleaved2/odd-oracle.py /tmp/sd-d-interleaved2-debug
python3 experiments/track-d-packed32-adj/boundaries.py /tmp/sd-d-interleaved2-debug
python3 experiments/track-d-balanced-frontier/extremes.py /tmp/sd-d-interleaved2-debug
python3 experiments/track-d-interleaved2/compare.py --data /path/to/sample-d --build-dir /tmp/sd-d-interleaved2-build --report /tmp/sd-d-interleaved2-report.json --runs 15 --expected a4c76ed030bc7e365db33191f6cf74708fba7f25eb48d64c8c4279f2e57046a0
```

No dataset, output answers, credentials or compiled binaries are included. No Mac Docker was used.
