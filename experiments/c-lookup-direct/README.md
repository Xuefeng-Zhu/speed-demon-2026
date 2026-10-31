# Track C direct region lookup construction — experimental

`baseline.rs` is the exact selected parser source SHA-256 `f71a22c0642250010d967cfb493fbfb95bab01f1c3e4dedac0b93fb2987e80ef`; `combined.rs` is `76497615f1abc0bf28a7b0d1d18030ebc263ddf8587d98c263ea5fc9e8840538`. The candidate maps each three-uppercase-letter country code to a 26³ direct table, and presizes the region vector from the last sorted id; later inserts still grow it if necessary. Output countries are collected in first-seen order and sorted after aggregation. Dictionary, record parser and aggregation remain unchanged. These optimizations rely on official §2.3's three-uppercase-letter country codes, unique ascending ids and terminal LF; the record parser still relies on §2.2's documented guarantees. No data, credentials, hardcoded answers or external dependencies are included.

Instrumented lookup-only native ARM tests across 21 randomized processes gave median 8.01 ms baseline and 2.32 ms combined; country-only and presizing-only medians were 5.28 and 4.32 ms. `profile.py` and `profile-report.json` retain the diagnostic and raw values. The instrumented program exits before worker processing and does not measure official end-to-end runtime.

In full-data end-to-end ARM screens, 11 highly contended pairs gave candidate/baseline median wall 0.30617/0.18284 s; the 15-pair repeat gave 0.11987/0.12823 s, and a third 15-pair batch gave 0.10260/0.10816 s. Median CPU times in those batches were 0.87095/0.79387, 0.65990/0.67350 and 0.67418/0.68331 s. All 88 executions including warmups produced the published hash. This is a mixed local result; even the two less-contended apparent 5.1–6.5% gains do not establish Linux x86 or official performance. Raw timings are preserved. No Mac Docker was run.

The combined candidate passed 24 mixed reference corpora at each of five worker counts, and 20 additional reference comparisons covering 0, 1, 240, 513 and all 17,576 possible uppercase country codes, sparse last id 999999, unknown region ids, and workers 1/2/7/32. Some fixture sizes intentionally exceed the generator's 240-country shape to test the implementation. `boundaries.py` generates those tests; no datasets are stored. The candidate remains unselected pending target evidence and review.

From this archive's root, on Linux x86-64-v3 with Rust/Python installed, generate official full seed-1 data independently, then run serially:

```sh
rustc --edition=2021 -O -C lto=fat -C codegen-units=1 -C panic=abort -C target-cpu=x86-64-v3 experiments/c-lookup-direct/baseline.rs -o /tmp/c-lookup-base
rustc --edition=2021 -O -C lto=fat -C codegen-units=1 -C panic=abort -C target-cpu=x86-64-v3 experiments/c-lookup-direct/combined.rs -o /tmp/c-lookup-candidate
python3 experiments/c-rust-independent.py --source experiments/c-lookup-direct/combined.rs --seeds 24
python3 experiments/c-lookup-direct/boundaries.py
python3 experiments/c-lookup-direct/independent-review.py
python3 experiments/c-lookup-direct/independent-oracle.py
python3 experiments/c-lookup-direct/profile.py --data /path/to/generated-full-c
python3 experiments/c-nameowned/compare.py --baseline /tmp/c-lookup-base --variant /tmp/c-lookup-candidate --data /path/to/generated-full-c --runs 15 --report /tmp/c-lookup-x86.json
```

Repeat end-to-end paired timing batches with fresh outputs and no competing benchmarks. The comparator verifies every public full hash and reports CPU and process RSS; official warmed cgroup peak and scoring are separate. `country.rs` and `presize.rs` are independent ablations for attribution and are not selected.

An independent reviewer found no §2.3 correctness defect. Their reproducible test checked all 17,576 index values form a bijection and ran 32 baseline/candidate reference executions across 1/2/7/32 workers, including an empty lookup, duplicate country assignments, reversed country keys, sparse ids and all uppercase codes (`independent-review.py`). This does not establish target performance.

A second independent reviewer found no §2.3 defect and built a manual, independent aggregation oracle covering 52,729 sorted region rows across all 17,576 codes with repeated nonadjacent mappings, id 999999, 52,730 records, unused and unknown groups, BOMs, line endings and amounts. It matched the exact candidate at workers 1/2/7/32 with overflow checks (`independent-oracle.py`).
