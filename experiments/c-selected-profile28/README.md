# Selected C phase diagnostic — not a performance candidate

`baseline.rs` is byte-identical to the selected C source at preparation, SHA-256 `8249f318e26050cc1a12f2be091344bf431ceb862665a3312bb29a92e140057d`. `profile.rs` has SHA-256 `1c28b57e3ead5c706652e1697a3b3f4ae33128c5e472e99c5734960e62708847`. The sole changes insert an `Instant` at program start, at parse and reduction phase starts, and per-worker elapsed-time stderr logging. No production branch changes or stored input/outputs are included. Each timestamp, scheduling effect, thread startup, stderr lock and instrumentation can change the measured workload, so these are diagnostic timings, not a competitive benchmark or official cgroup measurement. Worker wall times overlap and must not be summed as CPU usage. The published input's compact path is assumed by the diagnostic labels; the original noncompact fallback remains functional, but has no parse/reduce log labels and the runner deliberately rejects it.

A non-PGO ARM release build of `profile.rs` ran once against existing independently generated full seed-1, returned zero and produced SHA-256 `d8088b1cd42ba1338b1345b107b55db7b96ef1f5066f3ff64fd26a8912a0f536`. The one cold/variable ARM timing is not a performance result. No Docker or x86 execution was done.

For a serial x86 diagnostic on full seed-1 already available locally, with a compatible compiler and target ISA:

```sh
rustc --edition=2021 -O -C lto=fat -C codegen-units=1 -C panic=abort -C target-cpu=x86-64-v3 profile.rs -o /tmp/sd-c-profile28
python3 run.py /tmp/sd-c-profile28 /path/to/full-seed-1 > /tmp/sd-c-profile28-report.json
```

`run.py` performs one warmup plus ten instrumented runs, verifies the published output hash every time and reports per-run and median timing. Use no competing benchmarks; save all JSON. Compare phases within each instrumented run, not with independent uninstrumented official timing or across hosts. If available without privileges or system changes, a separate sampling profile of the uninstrumented baseline may help explain hot functions. Do not change sysctls, install privileged tools, delete user data, use Mac Docker, or assume native RSS proves an 8 GiB parent-cgroup bound.

Parent-run dot VM x86 instrumented diagnostic had 22 full-seed hashes pass across two batches. Median parse phases were 40.25 and 39.06 ms, reduction phases 46.57 and 36.59 ms, and total instrumented times 97.40 and 86.61 ms. Both phases were substantial and reduction varied. Timer, stderr and scheduling overhead perturb the work; overlapping worker-wall sums are not CPU time, and these numbers are neither official scoring nor a clean comparison with uninstrumented builds.
