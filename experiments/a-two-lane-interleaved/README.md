# A two-lane field-interleaved parser (unselected)

The exact selected compact baseline `baseline.rs` is SHA-256 `4af40353f517f566217b0f882ec25d8002f61d211dcc479c53f8a1dd5de7ed88`; isolated `candidate.rs` is `b98d76ca3d17b959c43c01c33c227d9614196710d4733a68be1b03829c560b0c`. Each parser splits its existing newline-aligned chunk into two newline-aligned intervals. While both are nonempty, it reads their timestamp, method and endpoint-scan fields in an interleaved loop, then performs both local dictionary mutations sequentially and appends both records. Each lane's remainder is parsed by the scalar helper. The same worker owns both intervals, one table and its per-hour compact/escape vectors; ranks are derived after parsing. No input ordering, seed, endpoint or cached answer is assumed. Empty or collapsed halves are legal.

Independent static review found no concrete coverage, ID-growth, compact/escape ordering or hash defect under the official grammar. In addition to 0/1k/100k/100k independent synthetic output checks, `coverage.py` instrumented actual input cursor visits: 48 combinations of empty, singleton, uneven and 2,500-record/2,114-endpoint data with 1/2/3/7/12/32 workers had each original record offset visited exactly once and matched the official reference; 48 more passed with all table hashes forced to zero. The candidate also passed empty, 40k all-escape, 40k alternating and 87,192-record/2,422-endpoint compact stresses at workers 1/2/3/7/12/32; 14 page-end sizes at workers 1/2/3/6/12/64; and a 132,624-group latency grid at workers 1/2/6/12/64. These were native macOS ARM with the anonymous mmap flag changed only in the test build.

The independent `../a-two-lane-independent/run.py` appended a test-only direct-parse property to this exact source and compared decoded `(endpoint, latency, error)` multisets for all 2,145 line-aligned subranges of a 64-record corpus plus 209 ranges of a 2,500-record corpus with over 2,048 endpoints. Normal and forced-zero-hash release-semantics tests passed. Two additional overflow-checked builds passed after explicitly converting the unchanged baseline SWAR arithmetic in `parse_latency` to equivalent test-only wrapping operations. The unmodified source intentionally relies on release overflow semantics; an initial unmodified `overflow-checks=yes` test failed in that existing SWAR code, so no claim is made that it supports checked arithmetic unchanged.

Two randomized native ARM warm-cache comparisons, 15 pairs after one warmup each, gave baseline/candidate wall medians `0.039396/0.038523` s and `0.041424/0.036837` s; CPU medians were `0.188320/0.181720` and `0.190687/0.182579` s. Median process RSS was approximately 260 MiB for both. All 64 full output hashes, including warmups, matched the published seed-1 hash. Host and batch variability is material; ARM process RSS and timing are not x86, official scoring-box or cgroup results. Actual Linux x86 and holdout behavior remain unverified. No Docker was run on the Mac.

## Target validation

From the extracted archive root, independently generate the official full seed-1 input and use the supported x86-64-v3 Linux target. The archive includes no datasets, credentials, executables or cached answers. Avoid concurrent benchmark work. The `coverage.py` instrumentation deliberately changes the test copy and emits cursor positions; it is not a scored binary.

```sh
python3 experiments/a-two-lane-interleaved/coverage.py
python3 experiments/a-two-lane-interleaved/coverage.py --force-collision
python3 experiments/a-two-lane-independent/run.py
for n in baseline candidate; do
  rustc --edition=2021 -O -C lto=fat -C codegen-units=1 -C panic=abort -C target-cpu=x86-64-v3 "experiments/a-two-lane-interleaved/$n.rs" -o "/tmp/a-lane-$n"
done
python3 track-a-verification/test.py --binary /tmp/a-lane-candidate --io directories
python3 track-a-verification/page_end_test.py --binary /tmp/a-lane-candidate --reference official/reference/a_ingest.py
python3 track-a-verification/latency_grid_test.py --binary /tmp/a-lane-candidate
python3 experiments/a-compact-records/stress.py --binary /tmp/a-lane-candidate --reference official/reference/a_ingest.py
python3 experiments/a-two-lane-interleaved/compare.py --baseline /tmp/a-lane-baseline --candidate /tmp/a-lane-candidate --data /path/to/full-a --report /tmp/a-lane-x86-a.json --runs 15 --threads 12
python3 experiments/a-two-lane-interleaved/compare.py --baseline /tmp/a-lane-baseline --candidate /tmp/a-lane-candidate --data /path/to/full-a --report /tmp/a-lane-x86-b.json --runs 15 --threads 12
```

Both target comparisons must verify the published output SHA-256; report CPU and process RSS separately from official `memory.peak`. Test all-escape and independent adversarial references as appropriate. The stronger x86 tests and any official practice are still pending; retain the baseline until reviewed results justify a trial.
