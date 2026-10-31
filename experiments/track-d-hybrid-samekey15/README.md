# D hybrid equal-minimum batching (unselected)

`baseline.rs` is exact selected capped hybrid SHA-256 `671c639be3400209e83e080dfb54947affd30ca71dc34ec17804d24d70292d9c`. `batch4.rs` is SHA-256 `fa36f3bbfa3ec9e6a92fd787ada415c5e257cdf1ea62a2a2fcf23718c3d5c1c0`; `batch16.rs` is `7fd333be25133a78264cb4b84441de46d4c8bcbfd73914af23761f23d8c47f17`. Other bounded variants are comparison controls. No selected source is changed.

After both heap minima are materialized and the original stop/side decision is made, a bounded number of entries are popped from the selected side's zero bucket. All have the same minimum key; zero-weight relaxations may add more entries at that key. Scheduling and the stop test are reconsidered after at most 4 or 16 pops. Delaying a stop can do additional work but does not remove a shorter path. Stale-key checks, cutoff marking, pool exhaustion, touched cleanup and exact indexed-wide rerun are retained. An independent static review found no concrete correctness defect. Additional work may change the number of fallback allocations or pool exhaustions for valid hidden inputs; the full 8 GiB parent-cgroup bound remains unproved, exactly as for the selected hybrid.

On verified public full seed-1, a randomized five-way nine-pair native shared ARM screen gave wall medians baseline/batch4/batch8/batch16/batch32 of 0.252384/0.244925/0.248341/0.245962/0.245681 s. A separate randomized 15-pair baseline/batch4 repeat was 0.254301/0.246909 s, about 2.9% lower wall; CPU was 1.811412/1.781434 s. All 82 full runs including warmups matched the published hash. Max process RSS in the repeat was 584,564,736/612,532,224 bytes; process RSS is not parent-cgroup memory. `screen.json` and `repeat.json` contain raw observations and flags. These shared ARM results do not establish Linux x86 or official scoring-box speed.

Exact batch4 and batch16 debug/overflow builds each passed seven forced capacities 0/1/2/15/16/17/65,536 against 16,000 random Dijkstra answers per build, 36,864 exhaustive answers, cutoff−1/cutoff/cutoff+1, the 2^21 node-format boundary, max-size maximum-weight chain and 6,000 repeated/unreachable queries. Instrumented exact-source `oracle4.py` passed 18,012 independent answers over 112 graphs with 78,915 actual second-or-later batch pops; `oracle16.py` passed the same count with 233,324 such pops. The pools retain the original 65,536-entry cap per direction. `run-forced.py` passed actual pool-exhaustion-triggered cleanup and fallback for caps 0/1/2 in temporary copies of both batch4 and batch16; repeat it on the target before evaluating performance.

For Linux x86 validation, verify CPU x86-64-v3 support before compilation, then run from the extracted archive root:

```
python3 experiments/track-d-hybrid-samekey15/verify4.py
python3 experiments/track-d-hybrid-samekey15/run-forced.py
python3 experiments/track-d-hybrid-samekey15/compare.py --data /path/to/full-d --build-dir /tmp/sd-batch-a --report /tmp/sd-batch-a.json --runs 15 --names baseline batch4 --seed 1948
python3 experiments/track-d-hybrid-samekey15/compare.py --data /path/to/full-d --build-dir /tmp/sd-batch-b --report /tmp/sd-batch-b.json --runs 15 --names baseline batch4 --seed 82811
```

The comparator builds x86-64-v3 on x86, randomizes paired order and checks the published full output hash. Test output and process RSS do not prove hidden-data correctness or cgroup peak. Measure the latter only where the parent-cgroup interface actually exists. No dataset, credentials or binaries belong in the archive. No Mac Docker was used.
