# D hybrid lazy opposite top (unselected)

`baseline.rs` is the exact selected hybrid source SHA-256 `671c639be3400209e83e080dfb54947affd30ca71dc34ec17804d24d70292d9c`; `candidate.rs` SHA-256 `50bd42988224e2d4ab34d024d2edd76813c6ccc7a5e6c6300139600f48a94932`. Only the narrow-search scheduling changes. The pool cap, cutoff, exact indexed-wide rerun and all memory allocations remain unchanged. This is a rebase of the earlier neutral lazy-top idea onto the current bounded linked pool, not selected code.

The side with fewer queued entries is selected before materializing a minimum; ties compare the two heaps' previous radix `last` keys. The chosen side's true minimum is obtained with `top`. For the nonempty opposite monotone heap, `last` is a lower bound on its actual minimum; stopping only if the chosen minimum plus that lower bound is at least `best` is therefore conservative relative to the ordinary two-top stopping test. A weaker bound can cause extra work. Ties may choose a different search order, but each direction still pops its own minimum. This is a proof sketch, not a proof of all implementation or hidden-data behavior.

`verify.py` compiled the exact source with optimization, overflow checks and debug assertions at caps 0, 1, 2 and 65,536. Its actual `FastHeap` lower-bound/multiset model checked 250,000 operations with zero/equal keys, resets and two heaps. Every build passed 80 random graph/16,000 independent Dijkstra answers, 4,096 exhaustive directed three-node graphs/36,864 all-pairs answers, cutoff−1/cutoff/cutoff+1, zero/self/unreachable and n=2^21/2^21+1 boundary tests. The cap-1 and default builds passed a full-size maximum-weight chain and 6,000 repeated/unreachable queries. `run-forced.py` separately asserted that caps 0/1/2 clean partial state and request the exact wide fallback. These are finite checks, not complete hidden-data, x86 or 8 GiB cgroup proof.

One randomized, serialized 15-pair native shared-Mac ARM full public seed-1 screen after a warmup produced the published output SHA-256 on all 32 runs. Median candidate/baseline wall was **0.281077/0.251350 s** (candidate 11.8% slower), CPU **2.026754/1.820729 s** (11.3% higher), and maximum native process RSS **613,318,656/613,171,200 bytes**. These are native process figures, not target x86, official scoring-box or parent-cgroup measurements. Given the clear regression, no repeat or target test was run; candidate stays unselected. Raw timings are `arm-a.json`.

To reproduce without Docker, independently provide the full seed-1 data and run:

```sh
python3 experiments/track-d-hybrid-lazy-top/verify.py
python3 experiments/track-d-hybrid-lazy-top/run-forced.py
python3 experiments/track-d-hybrid-lazy-top/compare.py --data /path/to/full-d --build-dir /tmp/sd-d-lazy --report /tmp/sd-d-lazy-report.json --runs 15 --seed 416719
```

The comparison script verifies each output hash and reports native process RSS. Target x86 and cgroup behavior remain untested. No Mac Docker was used.
