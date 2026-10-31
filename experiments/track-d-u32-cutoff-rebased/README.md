# Packed D with u32 cutoff and exact fallback (unselected)

This experiment is based on the packed-adjacency source `baseline.rs` from the official trial (`793d13729fe4dabe2a1ed272fef78e19567456676ed8df52c075bc4ac33ebd05`). `candidate.rs` adds a per-worker narrow bidirectional search. The narrow state stores complemented u32 distance pairs; values at or above `u32::MAX` are never inserted. If the narrow search found an answer below the cutoff, it returns that answer. Otherwise, if any relaxation was discarded at the cutoff, it repeats the query with the unchanged exact u64 search. If no relaxation was discarded, it returns the narrow result, including unreachable.

Why the exits are exact: edge weights are nonnegative. Any path beating a result strictly below the cutoff has every prefix and suffix below the cutoff, so the narrow search cannot truncate it. When no edge relaxation was discarded, the explored search is identical to the original u64 algorithm through its usual termination point; the original termination proof therefore applies, even if the result is at/above the cutoff or unreachable. The discard flag is conservative: it is set even if that tentative distance could not improve its destination. When the flag is set and no sub-cutoff answer was found, the original wide search runs from clean state. Both searches clear their touched cells and heaps after every nontrivial query.

Independent static review found no cutoff, fallback or state-cleanup defect under the official graph bounds. An overflow/debug-checked candidate passed 16,000 random independent Dijkstra queries, all 36,864 all-pairs queries over 4,096 directed three-node graphs, exact cutoff−1/cutoff/cutoff+1/zero/unreachable tests, a full-size maximum-weight chain, and 6,000 repeated/unreachable queries. `run-cutoff.py` additionally checks explicit no-discard and discard branches, wide results, fallback, and repeated narrow/wide state reuse. These tests do not prove every execution schedule or legal input.

Two randomized 15-pair native ARM **sample** batches, with independent order seeds and one warmup each, produced the published sample hash in all 64 executions. Candidate/baseline median wall times were `0.018233 / 0.020661` and `0.017908 / 0.020281` seconds; median CPU `0.092614 / 0.105289` and `0.092167 / 0.103864` seconds; maximum native RSS `38,109,184 / 55,623,680` and `38,518,784 / 54,984,704` bytes. The host is shared, runs are short, and native process RSS is not cgroup memory. This sample is not evidence of full-scale, x86, or official performance. Raw timings and flags are in `sample-arm.json` and `sample-arm-repeat.json`.

This is experimental and unselected. On queries requiring fallback, a worker retains both its narrow and u64 search arrays, increasing memory relative to the baseline; neither a full 8 GiB bound nor target cgroup use has been established. SHA-256 baseline: `793d13729fe4dabe2a1ed272fef78e19567456676ed8df52c075bc4ac33ebd05`; candidate: `5c07ea85035e37157f77c66ccd06d86cefd022cc42311aa95497f78dc4a6d451`.

For serialized native Linux x86-64-v3 full-data testing, extract at the archive root, generate official full seed-1 data independently and replace `/path/to/full-d` below. The comparator uses matching offline Rust compiler flags, warms each executable, randomizes within pairs, verifies the full public seed-1 hash on each run and records wall time, process CPU and native RSS. Run an additional batch with a different seed; Linux RSS is KiB and is not the official warmed cgroup peak.

```sh
python3 experiments/track-d-u32-cutoff-rebased/compare.py --data /path/to/full-d --build-dir /tmp/d-u32-rebase-build --report /tmp/d-u32-rebase-a.json --runs 15 --seed 8681
python3 experiments/track-d-u32-cutoff-rebased/compare.py --data /path/to/full-d --build-dir /tmp/d-u32-rebase-build --report /tmp/d-u32-rebase-b.json --runs 15 --seed 26461
python3 experiments/track-d-u32-cutoff-rebased/run-cutoff.py
python3 experiments/track-d-u32-fallback/thresholds.py /tmp/d-u32-rebase-build/candidate
python3 experiments/track-d-balanced-frontier/oracle.py /tmp/d-u32-rebase-build/baseline /tmp/d-u32-rebase-build/candidate
python3 experiments/track-d-balanced-frontier/exhaustive.py /tmp/d-u32-rebase-build/baseline /tmp/d-u32-rebase-build/candidate
python3 experiments/track-d-balanced-frontier/extremes.py /tmp/d-u32-rebase-build/baseline /tmp/d-u32-rebase-build/candidate
```

No datasets, credentials, binaries, generated answers or third-party code are in the transfer archive. No Mac Docker was used.
