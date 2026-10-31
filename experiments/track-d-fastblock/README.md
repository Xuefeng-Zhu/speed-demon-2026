# D exact reciprocal block assignment (experimental)

`baseline.rs` is the exact selected source (SHA-256 `1022f4d9c9956b17fd054e96a26d09551eff61936a851edf88505e12e2b1946c`). `meeting.rs` (SHA-256 `5e83f8facb4a7fca124289778b8d2b1fbd4b7e4806e94c1f926e0822e73d6b07`) computes each edge's forward/reverse CSR block using a precomputed floor(2^64/n) reciprocal, multiply-high and one exact remainder correction rather than runtime integer division. For `n=1` all valid node IDs are zero. For every representable u64 numerator, floor-reciprocal error is less than one, so the tentative quotient is exact or one low; `q*n <= x` and the correction are safe. The existing implementation also assumes `u*threads` fits machine usize; real 64-bit scoring-box worker counts and official node bounds satisfy this.

On shared ARM Mac, seven randomized measured full seed-1 pairs after warmup all matched the published hash. Candidate median wall 0.26578 s versus baseline 0.26674 s; CPU 1.86545 versus 1.85043 s. This is effectively tied, process RSS is not official cgroup memory, and x86 divider and multiply-high performance may differ. The ARM release assembly replaced two division instructions with multiply-high; this is not an x86 performance claim.

Both candidates passed 80 random directed graphs / 16,000 independent Dijkstra queries, 4,096 exhaustive directed three-node graphs / 36,864 queries, full-size maximum-weight chain and 6,000 repeated/unreachable queries. A separate Rust overflow-checked test extracted the candidate's exact closure and passed 6,216,009 mathematical comparisons, including n=1..256, node/block-cut boundaries, thread counts including large representable products, full n=1,740,512 boundaries, and 2 million deterministic random cases. Forced 1/2/3/7/12/32 worker binaries, compiled with overflow checking, each passed n=1 self-loops and the random oracle (96,000 total queries). No x86, Linux cgroup or official score is claimed. No Mac Docker was used.

On a compatible x86-64-v3 Linux host using separately generated full seed-1 data, serialize the following with other timing work:

```
python3 experiments/track-d-fastblock/compare.py --data /path/to/full-d --build-dir /tmp/d-fastblock-build --report /tmp/d-fastblock-x86.json --runs 11
python3 experiments/track-d-fastblock/reciprocal-property.py
python3 experiments/track-d-fastblock/worker-boundaries.py
python3 experiments/track-d-balanced-frontier/oracle.py /tmp/d-fastblock-build/baseline /tmp/d-fastblock-build/meeting
python3 experiments/track-d-balanced-frontier/exhaustive.py /tmp/d-fastblock-build/baseline /tmp/d-fastblock-build/meeting
python3 experiments/track-d-balanced-frontier/extremes.py /tmp/d-fastblock-build/baseline /tmp/d-fastblock-build/meeting
```

The randomized comparator verifies every full hash and records wall time, CPU and process RSS; Linux RSS is KiB, not cgroup memory. Run an additional repeat if results are close or noisy. No datasets, credentials, generated answers or binaries are included.
