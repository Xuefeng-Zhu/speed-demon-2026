# Biased balanced frontier (not selected)

The four isolated candidates multiply one side's heap count by two or four before choosing a side. `f2`/`f4` favor forward and `b2`/`b4` favor backward. All retain per-side minimum ordering and the same exact termination bound. Baseline is selected balanced-frontier D. A positive scaling of heap counts changes only which side is expanded, so the original nonnegative-edge correctness proof still applies; these variants were not independently oracle-tested.

On shared native macOS ARM, six randomized rounds including one warmup produced the published full-seed output hash on every run. Five measured median walls were baseline 0.314418 s, f2 0.337258 s, f4 0.336330 s, b2 0.418327 s and b4 0.438131 s. Raw measurements are `mac-arm-report.json`. This local screen is not an official or x86 score. No variant was selected; no Mac Docker was used.

For reproduction compile each `.rs` with identical optimized Rust flags, randomize their execution order on separately generated full data with `SD_DATA` and `SD_OUT`, hash every result and measure the target cgroup independently.

A separate one-run instrumented native ARM profile (`query-profile.rs`, `query-times.txt`) recorded per-query elapsed times while retaining the selected algorithm; the full hash matched. Across 2,000 queries the summed worker time was about 2,334 ms, with the slowest 10 accounting for 15.2% and slowest 100 for 59.9%. Initial memory faults, scheduling and instrumentation affect these values; they only show a heavy tail and do not establish an effective scheduling policy or official score.
