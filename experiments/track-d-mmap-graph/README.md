# Track D graph mapping (experimental, not selected)

`baseline.rs` is the exact selected Track D source (SHA-256 `f950514fc718d915f2392af72394ab2cdad8f44023a54396cdc32eff84120f4d`; candidate SHA-256 `854ee97ea0e74e80c7384976dbf68b5521ef3ea48a5e41d827daa6ebcec4d163`). `meeting.rs` maps the read-only, immutable graph file once with `mmap(PROT_READ, MAP_PRIVATE)` and gives each worker its original byte range from the map rather than copying separate ranges with positioned reads. The header, partition and graph algorithms otherwise remain unchanged. Mapping failure is checked; the map intentionally lives until process exit, and no writable mapping or dataset-dependent shortcut is used. The file must remain stable and must not be truncated while the process runs, as required by the task's immutable input environment.

Two randomized 11-pair warmed native ARM Mac full-seed batches after one warmup per binary matched all 48 output hashes. Median wall candidate/baseline 0.35301/0.38285 s (7.8% faster) and 0.28839/0.29974 s (3.8% faster); median CPU 1.70294/1.71409 s and 1.85088/1.85513 s. Max native RSS candidate/baseline 548,913,152/535,543,808 and 548,372,480/534,315,008 bytes. Host sharing and order effects make these noisy and nonofficial; `report-prior.json` and `repeat-prior.json` contain individual samples; these compared the earlier pre-THP baseline. This does not measure Linux x86 performance, cgroup memory accounting or cold-cache behavior. The official harness prewarms data, but page residency and map accounting differ across OS and cgroups. No Mac Docker was used.

Before the THP rebase, the candidate passed 80 randomized directed graphs / 16,000 Dijkstra queries, 4,096 exhaustive three-node graphs / 36,864 Floyd–Warshall queries, a max-size max-weight chain, and 6,000 repeated/unreachable queries. `worker-boundaries.py` additionally passed 96,000 random-oracle queries and n=1 at worker counts 1/2/3/7/12/32 with overflow checks; `boundaries.py` passed 63 randomized graph/reference cases covering cuts inside digits, spaces and newlines with workers 1/2/3/6/9/12/32, including zero-edge graphs.

From the extracted archive root, compile offline and run:

```
python3 experiments/track-d-mmap-graph/compare.py --data /path/to/full-d --build-dir /tmp/d-mmap-build --report /tmp/d-mmap.json --runs 11
python3 experiments/track-d-balanced-frontier/oracle.py /tmp/d-mmap-build/meeting
python3 experiments/track-d-balanced-frontier/exhaustive.py /tmp/d-mmap-build/meeting
python3 experiments/track-d-balanced-frontier/extremes.py /tmp/d-mmap-build/meeting
python3 experiments/track-d-mmap-graph/worker-boundaries.py
python3 experiments/track-d-mmap-graph/boundaries.py
```

The comparator randomizes paired order, uses matching build flags, validates the published full output hash after each run, and measures native per-process RSS, not official cgroup peak. Run isolated and repeat. Before promotion, review mmap lifetime and exact target behavior, test Linux x86 and official sandbox, and measure cgroup peak. No datasets, answers or credentials are in this package.

## Rebased candidate and independent review

The exact candidate above preserves all THP behavior at `bc902c7`; on Mac the Linux-only advice is compiled out. The parent independently confirmed this exact source against 80 random graphs at five worker counts, 36,864 exhaustive queries and 91 boundary graph/worker cases. A separate review found no mmap/lifetime defect under official immutable-file assumptions and passed 63 partition graphs at seven worker counts. Both tests exercised the Mac path; combined Linux THP and mmap need target validation.

Two 11-pair native ARM batches of the exact rebased sources each passed every full hash. First, mmap median wall 0.37597 s versus baseline 0.29492 s, CPU 1.77002 vs 1.82607 s; another verification was active. Repeat median wall 0.28747 vs 0.40877 s, CPU 1.80585 vs 1.85733 s. The wall ordering reverses under heavy shared-host contention, while median CPU decreased approximately 3% in each. Native RSS increased around 13 MB. `report.json` and `repeat.json` retain raw results. These are insufficient to establish a target win; retain current selected implementation until isolated x86 and official validation.
