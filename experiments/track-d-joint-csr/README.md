# Track D joint CSR build (not selected)

`baseline.rs` is the exact selected Track D source. `meeting.rs` constructs forward and backward CSR blocks in one scoped worker pool, with each worker owning disjoint `first` and `adj` slices for its block. The two directions still use exact independent buckets and cursors. Both graph buffers exist simultaneously during construction, so cgroup peak may differ from the baseline. No selected files changed.

A randomized nine-pair native shared macOS ARM full-seed screen, plus one warmup per source, matched all 20 official output hashes. Median wall candidate 0.39808 s vs baseline 0.38667 s; CPU 1.8710 vs 1.8540 s. Host contention was substantial; raw samples are `report.json`. This is not x86, cgroup, or official score evidence and the result does not support promotion.

Candidate passed 80 independent directed graph cases / 16,000 Dijkstra queries, 4,096 exhaustive three-node cases / 36,864 all-pairs Floyd–Warshall queries, a full-size maximum-weight chain, and 6,000 repeated/unreachable queries. Reproduce using `experiments/track-d-balanced-frontier/{oracle,exhaustive,extremes}.py` against a compiled candidate, and `python3 experiments/track-d-joint-csr/compare.py --data /path/to/full-d --build-dir /tmp/d-joint-build --report /tmp/d-joint.json --runs 9`. No Mac Docker used.
