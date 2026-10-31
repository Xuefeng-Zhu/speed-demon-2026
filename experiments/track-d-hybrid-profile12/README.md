# Current D hybrid phase and queue profile (diagnostic only)

`build.py` checks that `track-d/src/main.rs` is the exact selected hybrid source SHA-256 `671c639be3400209e83e080dfb54947affd30ca71dc34ec17804d24d70292d9c`, then writes a separate instrumented copy. It adds wall-clock phase markers and owner-local counters for narrow search, fixed-pool radix operations and exact-wide fallback. It does not modify the selected source or change its algorithms. Worker log lines occur after the worker finishes its assigned queries; the counters and logging can perturb runtime and scheduling.

One warmup pair and five randomized measured pairs of uninstrumented and instrumented binaries ran on the verified full public seed-1 data, with eight available native macOS ARM workers and no other intentionally concurrent benchmark. All 12 outputs matched SHA-256 `a23dbdf0a3e49cc8901310a9ee1dc6a9a569a85297b6da75c2a7002cb2ed277e`. Process wall medians were 0.257553 seconds uninstrumented and 0.264480 seconds instrumented, about 2.7% instrumentation overhead in these separate paired executions. CPU medians were 1.820945 and 1.913695 seconds. Native process RSS is not parent-cgroup memory.

Instrumented phase medians were 30.660 ms parsing/bucketing, 7.020 ms forward CSR, 7.051 ms reverse CSR, 44.875 ms total graph loading, 210.182 ms for query workers and 255.617 ms from `main` entry through output write. Medians are computed independently and do not necessarily sum. Worker timings overlap; these figures are diagnostic ARM observations, not official scoring-box or x86 timings.

Per full input the aggregated narrow search counted 20,975,615 `reach` calls (excluding 12 relaxation attempts discarded at the u32 cutoff), 8,654,879 successful updates, 7,573,418 pops including 449,706 stale pops, and 8,065,131 distinct touched-slot clears. It performed 1,821,199 radix redistributions: **32,522,386 linked-node visits for minimum scans and 32,522,386 further node moves**. The two values must be equal by this implementation's redistribution logic. Across workers there were eight exact-wide fallback queries, zero observed pool exhaustions and a maximum individual narrow heap of 2,721 live entries. The latter facts are observations of one public dataset, not limits for other valid data.

Queries dominate the observed instrumented wall time. Avoiding the separate linked-list scan might help, but caching a minimum also requires maintaining minima on normal insertions and redistribution; the counters alone do not establish an improvement. Any change requires exact priority-queue semantics, actual target benchmarking, adversarial forced-exhaustion checks and parent-cgroup assessment.

Reproduce with the existing generated full seed-1 data and a free, isolated native CPU window:

```sh
python3 experiments/track-d-hybrid-profile12/build.py /tmp/sd-d-profile12.rs
rustc --edition=2021 -O -C lto=fat -C codegen-units=1 -C panic=abort track-d/src/main.rs -o /tmp/sd-d-profile12-base
rustc --edition=2021 -O -C lto=fat -C codegen-units=1 -C panic=abort /tmp/sd-d-profile12.rs -o /tmp/sd-d-profile12-instrumented
python3 experiments/track-d-hybrid-profile12/run.py --baseline /tmp/sd-d-profile12-base --profile /tmp/sd-d-profile12-instrumented --data /path/to/full-d --report /tmp/d-profile-report.json --pairs 5
```

`arm-report.json` contains all raw warmup and measured samples, hashes, native process times/RSS and instrumented stderr. No generated dataset or binary is included. No Docker was run on the Mac.
