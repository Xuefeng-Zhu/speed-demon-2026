# Local optimization experiments

These measurements are for iteration, not official scores. All benchmarks used seed-1 full data, native macOS ARM builds, one warmup per variant, then five measured runs per variant. `benchmark.py` interleaves order, deletes the prior output, and checks every output against the official full SHA-256. No other candidate experiments were deliberately running during these comparisons. Uncontrolled system activity, cache behavior, compiler differences and CPU architecture still limit transfer to the x86 judging machine. See the JSON reports for each timing and exact binary invocation.

| Track | Baseline median | Candidate median | Local median ratio |
|---|---:|---:|---:|
| A: original vs chunked/select | 0.365936 s | 0.244733 s | 1.50× faster |
| B: original vs token views | 3.612033 s | 3.118447 s | 1.16× faster |
| C: original vs input views | 2.636044 s | 1.499528 s | 1.76× faster |
| D: 12 vs 6 workers | 1.018773 s | 1.102140 s | 6 workers 8.2% slower |
| D: 6 vs 3 workers | 1.110951 s | 1.422599 s | 3 workers 28.1% slower |

For D, a separate earlier local per-process measurement recorded roughly 766 MB peak RSS for 12 workers and 515 MB for 6; 3 used around 381–388 MB in a noisy run. Six is a provisional compromise because memory also contributes to the score. These macOS RSS values and times are not the judge's cgroup memory or execution measurements; confirm the worker choice on the board.

Compile A–C using `c++ -std=c++17 -O3 -DNDEBUG` for both the preserved original `track-<letter>-agent/main.cpp` and current `track-<letter>/main.cpp`. D's baseline reconstruction is in `track-d/PERF.md`. The corresponding JSON files contain all measurements and exact arguments. `/tmp` paths refer to locally generated inputs, and can be recreated with the official generators. Example for A after compiling:

```sh
python3 experiments/benchmark.py --baseline '/tmp/speed-bench/a-old /tmp/speed-demon-a-full/requests.log /tmp/speed-bench/a.txt' --candidate '/tmp/speed-bench/a-new /tmp/speed-demon-a-full/requests.log /tmp/speed-bench/a.txt' --output /tmp/speed-bench/a.txt --expected 495ca09682b9673ef836a506496177680bb4a3af54255174befddb1f83481cd3 --runs 5 --report experiments/bench-a.json
```

`differential.py` compiles the current candidate sources, generates inputs, runs the official reference, and compares bytes. Three tiny seeds (2, 17, 4242) passed for all four tracks; JSON reports retain their hashes. The separate `a_chunk_boundaries.py` test passed nine deliberately placed 1 MiB splits spanning a maximum-length log line. `x86.md` records the non-destructive x86 sample checks.

## Additional experiments

`a-output-buffered.cpp` matched full seed 1, seed 999 sample, and independent synthetic tests; an eight-pair native Mac experiment suggested a roughly 7% trimmed-mean improvement. `b-zero-copy.cpp` matched full seed 1 and alternate-seed/randomized tests, with a roughly 17% native median improvement in three contended paired runs. `track-d-sparse/src/main.rs` matched full seed 1, with similar local speed and lower observed memory in three pairs. These are experimental alternatives, not the selected submissions; their x86 and competition-container performance and scoring effects remain unverified. See the accompanying reports where present.
