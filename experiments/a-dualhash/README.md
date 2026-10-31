# Track A two-lane endpoint hash

`baseline.rs` is the exact auto-worker Track A at e8e828a (SHA-256 9aa7eb44c30fbfc5b701ff9467d26b0a27e765520c5e766ef90d0ea6b04d85fc). `dualhash.rs` (SHA-256 b5cda962e03226d501e8c61003f656e3dc738bd798b2ead1a5900612b525138f) alternates endpoint words across two independent hash lanes while scanning for the delimiter. Full endpoint bytes are still compared on hash matches; all output computation and bounded data structures are unchanged. This is experimental and not selected. Neither mixer provides a general hash-flooding guarantee.

On a shared Apple ARM host, twelve randomized measured full-seed-1 runs after one warmup gave medians: 12 workers 0.043292 s candidate vs 0.045446 s baseline, and 6 workers 0.046366 vs 0.047468 s. Every output SHA matched. Measurements are noisy native timings with contention, not scoring-machine results; raw samples are in `dualhash-bench.json`. For these Mac-only tests, a temporary source copy changed Linux MAP_ANONYMOUS 0x20 to Darwin 0x1000, with no other changes. Release load-bounds and hour-vector-reservation experiments plus an oversubscription screen did not improve; raw data are included.

The candidate passed the independent four-case synthetic oracle, 14 exact page-edge sizes across six worker counts, the 132,624-group latency grid across five worker counts, and official tiny seeds 2/17/99/4242 across three worker counts. These checks do not establish hidden-data correctness or x86 performance.

The following paths apply to the Library transfer archive. In this repository, the same verification scripts are under `../../track-a-verification/` and the reference is under `../../official/reference/`. On Linux x86 with Rust and independently generated full data:

```
python3 compare.py --data /path/to/full-a --threads 12 --runs 9 --report /tmp/a-dual-report.json
rustc --edition 2021 -O -C lto=fat -C codegen-units=1 -C panic=abort -C target-cpu=x86-64-v3 dualhash.rs -o /tmp/a-dual
python3 tests/test.py --binary /tmp/a-dual --io directories
python3 tests/page_end_test.py --binary /tmp/a-dual --reference official/reference/a_ingest.py
python3 tests/latency_grid_test.py --binary /tmp/a-dual
```

The comparison checks the full published hash every run and captures per-process CPU and RSS. Linux process RSS is not official cgroup memory. `--generic` disables x86-64-v3. There are no datasets or credentials in this archive. Please test on target before considering board promotion.

Independent review additionally compared the candidate and a test-only forced-zero-hash build against the official reference on 1,803 endpoint patterns spanning lengths 1–125, all 72 hours, extreme status/latency values, and worker counts 1/2/3/7/12/32. Both matched SHA-256 `dd9fecaf57f04ea2aee754a4e02a22aaf0a081ef035513346aa40beb2f229919`. `stress-portable.py` reproduces this check when passed the reference and executable paths. Native ARM with Darwin mmap adaptation; not an official score.

A further 2,422-endpoint fixture forced table growth beyond the official generated vocabulary bound. Candidate and forced-zero-hash builds matched reference at all six worker counts, SHA-256 `99451cbcc332baf1e2acca2cdd03eb297d121faa3c3e861ef2fcb7115a242a14`; `stress-growth.py` reproduces it.

A speculative first/last-word hash (`ends-bench.json`) was slower than two-lane hash in ten randomized ARM pairs and can cluster paths with shared prefixes and suffixes. It was not selected.
