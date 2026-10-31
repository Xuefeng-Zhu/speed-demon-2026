# Current B phase diagnostics (native ARM; not a candidate)

`baseline.rs` is the selected Track B source, SHA-256 `7d371fe84ce9f0fd9d3c7e6fdf02b6b37e0f1440319c654161b990cf27bb8bf3`. `profile.rs` adds `Instant`/stderr diagnostics around its existing phases, each index worker, and each 256-query answer block; it does not change output logic. `profile-callback.rs` adds a clock around each document callback; its separate five-run observations are described below. None of these are selected code or target benchmark results.

On a shared native macOS arm64 host with rustc 1.95.0 and 8 available workers, one warmup and five measured runs of `profile.rs` all produced the published full seed-1 output hash `f86973c210228141bcb6f1f1b10188ad2a9b65f71e7cd7cf4590b38de4e80927`. Input file hashes also matched the official full seed-1 specification. Median reported wall phases were:

| Phase | Median |
| --- | ---: |
| Query reading | 0.226 ms |
| Query parsing and interning | 13.324 ms |
| Short table and mmap | 1.864 ms |
| Sample and phrase-anchor setup | 1.970 ms |
| Parallel indexing | 155.489 ms |
| Frequency/cache setup | 0.543 ms |
| Parallel query answers | 45.795 ms |
| Format and write | 6.229 ms |
| Instrumented main total | 225.244 ms |

Across eight overlapping index workers, the median sum of each worker's elapsed document-scan/phrase phase was 1.081 s and the median sum of its subsequent CSR construction was 0.0867 s. Those are **sums of overlapping elapsed durations**, not CPU times; the scan includes tokenization, document callback, phrase comparisons and scheduler effects. It indicates that the next useful question is where time goes *inside* the scan, rather than asserting phrase matching or token lookup is independently dominant. Median sum of overlapping elapsed answer-block durations was 0.358 s; there were 196 blocks, 50,000 queries and 31,000 Boolean queries per run.

The separate callback-instrumented run (one warmup and five measured, all matching the same hash) recorded median sums of overlapping worker elapsed time of 0.254 s inside document callbacks and 0.871 s in traversal/tokenization plus remaining per-document work, or roughly 23% and 77% of their 1.121 s combined elapsed sum. This groups callback stamping, postings and phrase work together; traversal includes token lookup, scanning, loop work, clock overhead and scheduling. The finer clocks increased instrumented-main median from 225.244 to 242.450 ms, so use this as a rough bottleneck clue, not exact attribution. Raw worker data are in `callback-report.json`.

Timings include many stderr writes and clock reads; diagnostics alter scheduling and timing. Reported process wall includes startup and Python overhead, and phase durations exclude some logging gaps. Native ARM uses the scalar classifier and is neither x86 AVX2 nor the scoring machine. The measured 8-worker split differs from the official 12-thread hardware. No target speed, cgroup-memory, or hidden-seed conclusion follows. Raw phase, worker and block timings are in `report.json`.

To reproduce on a host with a verified local copy of full seed 1:

```sh
rustc --edition=2021 -O -C lto=fat -C codegen-units=1 -C panic=abort \
  experiments/b-current-phase-profile/profile.rs -o /tmp/sd-b-current-phase-profile
python3 experiments/b-current-phase-profile/run.py \
  --binary /tmp/sd-b-current-phase-profile --data /path/to/full-b \
  --runs 5 --report /tmp/b-current-phase-report.json
```

`run.py` checks each output hash and saves raw measurements. Do not run competing workloads during the timing window. No generated input, credentials or binaries are included; no Mac Docker was used.
