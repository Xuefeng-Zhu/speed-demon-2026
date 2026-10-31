# Speed Demon D one-pass scanner comparison

`baseline.rs` is exact selected meeting-update source SHA-256 `2c4bcd2771cf79eceb37ee309edaeda4675db6f026458f483871f784a268755e`. `combined.rs` SHA-256 `d904778ad3f63986aff2c5074f4a708f92dd910955a01a3bdd9be4799d7bd8bd` adds the one-pass edge-number scanner. `prior.rs` is the previous pre-meeting baseline SHA `fa01c6bbda5b7264ad104832ef284003fb7cc37f6cfc56e7fdab409abb2a9047`; `scan.rs` is the scanner alone on that old baseline SHA `a9c444ee3eb3fe09f2d34047b0ad0c36ac108a8b04e8ab6cc327482535239437`. The primary comparison is baseline vs combined. All code computes full results; no datasets, credentials or binaries included.

On compatible x86-64-v3 with Rust installed and the official full seed-1 data generated separately:

```sh
python3 compare.py --data /path/to/full-d-data --build-dir /tmp/d-scan-build --report /tmp/d-scan-results.json --runs 5
python3 oracle.py /tmp/d-scan-build/baseline /tmp/d-scan-build/combined
python3 extremes.py /tmp/d-scan-build/baseline /tmp/d-scan-build/combined
python3 boundaries.py
python3 independent-review.py
python3 partition-simulation.py
```

The comparator compiles offline using x86-64-v3 on x86 by default (`--generic` disables), performs warmups, randomizes four-way run order, verifies every full-data hash, and measures wall/CPU/process RSS; RSS is not official cgroup memory. Scanner alone and combined passed 80 random graphs/16,000 independent oracle queries, full-size maximum-weight chain and 6,000 repeated queries. Seven measured shared ARM Mac pairs after warmup for scanner alone vs *prior* baseline gave 2.288 s vs 3.003 s; timings were very noisy (ranges 1.331–5.791 vs 1.387–4.157 s); CPU medians 3.927 vs 4.054 s. These are nonofficial and do not establish x86 performance. An independent seven-pair shared ARM comparison of combined vs selected meeting measured median 0.5959 s vs 0.6235 s, CPU 2.819 vs 2.902 s; ranges overlapped and all full hashes passed (`combined-review-report.json`). Independent review passed 63 graph fixtures that exercise digit, space and newline shard cuts across 1, 2, 3, 6, 9, 12 and 32 workers. Target testing is needed.

Additional independent review scripts passed 95,100 Floyd–Warshall answers across six worker counts and 5,600 partition simulations covering within-line offsets 0–26.
