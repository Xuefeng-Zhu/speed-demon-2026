# Track D graph mapping against restored baseline

`baseline.rs` is byte-identical to the selected Track D source at `451429c`, SHA-256 `1022f4d9c9956b17fd054e96a26d09551eff61936a851edf88505e12e2b1946c`. `meeting.rs`, SHA-256 `a50add1022e968ca5f3344b50bfa8fae3a57b449e685d820362c904fe9e2577b`, maps the immutable graph file once read-only with `mmap(PROT_READ, MAP_PRIVATE)` and uses the original worker byte ranges directly instead of copying with positioned reads. It does not include the discarded THP experiment. Mapping failure is checked; the map remains until process exit. The file must remain stable and not be truncated while mapped, as expected for the official prepared read-only input.

Two randomized 11-pair warmed native ARM Mac full-seed batches after one warmup per binary matched all 48 output hashes. Median wall candidate/baseline: 0.35301/0.38285 s and 0.28839/0.29974 s; median CPU: 1.70294/1.71409 s and 1.85088/1.85513 s. Max native RSS: 548,913,152/535,543,808 and 548,372,480/534,315,008 bytes. Host sharing and order effects make these noisy and nonofficial; `report.json` and `repeat.json` contain individual samples. Linux x86 performance, cgroup memory accounting and cold-cache behavior remain unverified. The official harness prewarms data, but OS and cgroup mapping accounting may differ. No Mac Docker was used.

The exact candidate passed 80 random directed graphs and 16,000 independent Dijkstra queries, 4,096 exhaustive three-node graphs and 36,864 Floyd–Warshall queries, a full-size max-weight chain, and 6,000 repeated/unreachable queries. `worker-boundaries.py` additionally passed 96,000 random-oracle queries and n=1 at worker counts 1/2/3/7/12/32 using overflow checks; `boundaries.py` passed 63 graph/reference cases covering cuts inside digits, spaces and newlines at 1/2/3/6/9/12/32 workers, including zero-edge graphs. An independent review found no mmap lifetime, partition or FFI defect under the official x86-64 immutable-input assumptions, and independently reran the 63 boundary fixtures.

From the extracted archive root, with Rust and Python installed and full seed-1 data generated separately:

```
python3 experiments/track-d-mmap-restored/compare.py --data /path/to/full-d --build-dir /tmp/d-mmap-build --report /tmp/d-mmap.json --runs 11
python3 experiments/track-d-balanced-frontier/oracle.py /tmp/d-mmap-build/meeting
python3 experiments/track-d-balanced-frontier/exhaustive.py /tmp/d-mmap-build/meeting
python3 experiments/track-d-balanced-frontier/extremes.py /tmp/d-mmap-build/meeting
python3 experiments/track-d-mmap-restored/worker-boundaries.py
python3 experiments/track-d-mmap-restored/boundaries.py
```

The comparator randomizes paired order, uses matching build flags, validates the published full output hash after each run, and measures native per-process RSS rather than cgroup peak. Repeat in isolation. Before promotion, test Linux x86 and the official sandbox and measure warmed cgroup peak. No datasets, answers or credentials are included.

## Dot VM x86 comparison

The parent-run native x86 paired batches reported 0.8–3.7% lower wall time with approximately 26% higher native RSS. Across this, C parser and B grouped packages, 164 full hashes, 24 alternate comparisons, Linux/AVX2 guard-page, collision, boundary and graph-oracle checks passed. These are not official scoring-box wall or cgroup-peak measurements; the selected source remains unchanged pending a controlled comparison.

Official mapped batches at `a9e1d0d` and `3ee91f3` measured 0.383379 s and 0.463912 s, against the preceding positioned-read baseline batch at 0.377822 s; all gates passed. No official wall-time improvement was established, so positioned reads were restored. These are separate batches and can vary.
