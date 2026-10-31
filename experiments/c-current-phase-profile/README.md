# Track C phase and owner-balance diagnostics

These diagnostics are **not selected submissions or competitive benchmarks**. `baseline.rs` is the exact selected fused C source, SHA-256 `6e12627e96f0a0433e567413ccacc1a5d7fdf2de8f4781a3f826c260499783dd`. `profile.rs` adds `Instant` timing and stderr output around setup, each parser and reducer, each parallel phase, and total runtime; `balance.rs` reports the number of events and dictionary rows per owner bucket. They change the measured program and include thread-level timer/output overhead. Worker elapsed time is **wall time**, not CPU time, and worker sums overlap. These results cannot predict the official x86 machine or cgroup score.

A fresh full seed-1 dataset was generated with `python3 official/generators/c_join.py --seed 1 --scale full --out /tmp/sd-c-profile-seed1`. A 10-run instrumented macOS ARM batch after one warmup produced the exact official full output SHA-256 `d8088b1cd42ba1338b1345b107b55db7b96ef1f5066f3ff64fd26a8912a0f536` each time. Median setup 3.820 ms, parse phase 44.371 ms, owner reduction 39.387 ms, total 92.788 ms. Sum of worker elapsed medians was 292.107 ms for parse and 260.403 ms for reduction; this is **not** CPU time. Median per-run reducer slowest/fastest worker elapsed ratio was 1.71, but timer/printing overhead, worker scheduling, memory locality and other activity can affect this ratio. See `arm-report.json` for every sample.

One separate diagnostic run on the same input also produced the expected output. Its eight owner bins held 403,227–441,529 events and 12,341–12,823 exact-name dictionary rows each (see `balance-report.txt`). Coarse event and row counts are reasonably close, but do not capture expensive-name equality, repeated group locality or per-worker runtime. They do not explain the observed timing skew or establish that additional owner partitions will help. The prior `c-owner-moreparts` experiment showed no reliable win against an older owner implementation. Potential large gains likely require tackling **both** the parsing and reduction phases or overlapping them safely; earlier lock/atomic/pipeline experiments are recorded under `experiments/` and showed regressions in preliminary screens. The data is a single public seed and does not establish hidden-input behavior.

To reproduce, generate the full data separately and run the binary and script serially with no competing benchmarks:

```sh
rustc --edition=2021 -O -C lto=fat -C codegen-units=1 -C panic=abort experiments/c-current-phase-profile/profile.rs -o /tmp/sd-c-profile-bin
python3 experiments/c-current-phase-profile/run.py /tmp/sd-c-profile-bin /path/to/full-c > /tmp/c-profile-report.json
rustc --edition=2021 -O -C lto=fat -C codegen-units=1 -C panic=abort experiments/c-current-phase-profile/balance.rs -o /tmp/sd-c-balance-bin
SD_DATA=/path/to/full-c SD_OUT=/tmp/c-profile-output /tmp/sd-c-balance-bin 2> /tmp/c-balance-report.txt
```

The user-generated data and output used for this screen were removed after both local agents finished. No Mac Docker was used. For x86 add the compatible `-C target-cpu=x86-64-v3` and treat results as diagnostics, then measure any candidate with an uninstrumented official run.
