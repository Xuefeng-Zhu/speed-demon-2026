# Track A dynamic range sweep

Compare exact selected Track A baseline with 2x, 4x, 8x and 16x line-aligned dynamic ranges per worker. Each worker retains one local endpoint table and hour vectors as it claims ranges. Input records and outputs are computed from the provided input; no data or answers are included. Each range calls `MADV_POPULATE_READ`, so its overhead may affect Linux differently from the native ARM Mac screen. The selected source is unchanged.

Nine randomized full-seed runs after two warmups on a shared ARM Mac all matched the published output hash. Median wall seconds baseline / 2x / 4x / 8x / 16x: 0.03943 / 0.03960 / 0.03738 / 0.03755 / 0.03807. Median CPU seconds: 0.19192 / 0.19381 / 0.19546 / 0.19667 / 0.19561. Native Mac binaries changed only the Linux anonymous mmap flag to Darwin's value. Timings overlap and are not x86, official, or cgroup evidence. The 8x variant also passed the independent empty/1k/100k/100k oracle and 14 page-end fixtures; prior independent 4x checks included those and a 132,624-group grid. The 2x/16x variants have only been full-hash screened.

On a compatible x86-64-v3 Linux VM, generate the official full seed-1 input separately and run serialized, with no competing benchmarks:

```
for n in baseline range2 range4 range8 range16; do rustc --edition=2021 -O -C lto=fat -C codegen-units=1 -C panic=abort -C target-cpu=x86-64-v3 "src/$n.rs" -o "/tmp/a-$n"; done
python3 tests/test.py --binary /tmp/a-range8 --io directories
python3 tests/page_end_test.py --binary /tmp/a-range8 --reference official/reference/a_ingest.py
python3 tests/latency_grid_test.py --binary /tmp/a-range8
python3 compare.py --baseline /tmp/a-baseline --candidate /tmp/a-range2 --data /path/to/full-a --report /tmp/a-range2.json --workers 12 --runs 12
python3 compare.py --baseline /tmp/a-baseline --candidate /tmp/a-range4 --data /path/to/full-a --report /tmp/a-range4.json --workers 12 --runs 12
python3 compare.py --baseline /tmp/a-baseline --candidate /tmp/a-range8 --data /path/to/full-a --report /tmp/a-range8.json --workers 12 --runs 12
python3 compare.py --baseline /tmp/a-baseline --candidate /tmp/a-range16 --data /path/to/full-a --report /tmp/a-range16.json --workers 12 --runs 12
```

The comparator randomizes paired order, warms both, uses fresh outputs and verifies every published full hash. It reports native process RSS, not official warmed cgroup peak. Run alternate-seed/reference and adversarial tests before selecting a variant; official scoring decides. This package has no credentials, datasets, binaries or cached answers. `official/LICENSE` covers copied official files.

## Dot VM results

The parent-run shared native x86 VM comparison found no consistent winner among the dynamic scheduling variants. Across that investigation, 350 full-hash executions, 80 alternate-reference comparisons and the boundary grid passed. The selected static scheduling was retained. These are native VM checks, not official measurements.
