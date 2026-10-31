# D current coarse-bucket diagnostic (not an optimization)

Baseline `baseline.rs` is byte-identical to selected D coarse source SHA-256 `2a2a325a1c87e4bc68c260e0d80353e0b8f1f9a7b5be81b1ffeaaede6d813f9d`. `profile.rs` adds diagnostic phase timers and per-thread counters for heap operations, stale entries, fallback and touched state; search logic remains unchanged. Timers, counters, stderr logging and scheduling materially perturb execution, so timings are diagnostic only; overlapping worker wall times are not CPU time, native process RSS is not parent-cgroup memory, and no competitive speed or cgroup conclusion follows. This archive contains only code, scripts and notes: no datasets, binaries or credentials.

Two randomized ARM paired sanity runs plus warmups on full seed 1 verified every output against the published SHA-256. Profiling overhead was substantial (~9.6% median wall in only two pairs), so do not use those timings to infer target performance. Initial counters show coarse-queue redistribution and exact fallback observations for this one public input only; a hidden graph can behave differently.

On an x86-64-v3 Linux host with independently generated full seed 1 already available and no competing benchmarks, compile using the matching compiler and flags, and compare instrumented to control:

```
rustc --edition=2021 -O -C lto=fat -C codegen-units=1 -C panic=abort -C target-cpu=x86-64-v3 baseline.rs -o /tmp/sd-d-base29
rustc --edition=2021 -O -C lto=fat -C codegen-units=1 -C panic=abort -C target-cpu=x86-64-v3 profile.rs -o /tmp/sd-d-prof29
python3 run.py --baseline /tmp/sd-d-base29 --profile /tmp/sd-d-prof29 --data /path/to/full-d --report /tmp/sd-d-prof29-report.json --pairs 5
```

The script verifies the published hash for every run and reports raw diagnostics. Inspect phase durations and sum counts across threads within each instrumented execution. Compare overhead with its paired control; do not compare these results to official timing or infer hidden-data memory bounds. Optional sampling of the exact uninstrumented binary is appropriate only if already permitted, without installing tools, changing sysctls, raising privileges or touching unrelated data. Do not run Docker on the Mac.
