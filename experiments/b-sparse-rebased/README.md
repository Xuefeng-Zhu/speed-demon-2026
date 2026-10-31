# Track B sparse Boolean evaluation, rebased

Compare the exact selected baseline `baseline.rs` (SHA-256 `322cc95ee08cf6d4abc5e1b52240753f66c7eaf89ab669cb6d72b0a8487dc458`) with `threshold512.rs` (SHA-256 `c2d41e1e001ad67d3b0a808ca65b3207fc528c34ba80bf308597d60cc5b361c4`). The earlier sparse comparison used a baseline without the current dense-popcount aggregation, so it did not isolate this change. This candidate preserves that aggregation and all baseline phrase handling and bitmap cap behavior.

When the sum of the operand posting lengths is at most 512, evaluate the query left to right with sorted set merges, and derive count, sum, and top ten from the sorted result. Intermediate sets cannot exceed the 512 total input postings. Larger queries use the unchanged bitmap path. `threshold128.rs` is an exploratory comparator, not the selected candidate.

On the shared native ARM machine, randomized paired full-seed batches gave 0.2609 vs 0.2748 seconds (9 pairs) and 0.2504 vs 0.2699 seconds (15 pairs), candidate vs baseline; median CPU fell 6.5% and 5.9%. All 52 full outputs including warmups matched the expected hash. Median native RSS was approximately 503–504 MiB, with variable peaks. Host load differed between batches. These are not x86, official scoring-machine, or cgroup results, and do not establish an official win.

The normal candidate passed 40 official-reference fuzz corpora, duplicate/overlapping phrases and 250,000-document duplicate stress, long-line/shard and alignment tests. Overflow-checked test-only always-sparse and zero-short-hash variants passed fuzz and algebra. The trace confirmed posting totals 511 and 512 select sparse and 513 selects bitmap. Independent review found no semantic defect and passed 5,379 threshold queries, three runs of 5,364 expressions across 64 membership assignments, and 310,536 reference comparisons across worker counts and zero/eight-byte bitmap caps; see `independent-review.md`. These are finite tests, not a proof for every input.

## Linux x86 comparison

From the extracted archive root, run on the intended x86 host, serialized with other benchmarks. Adjust the full dataset path. Actual AVX2 guard/page behavior, cgroup RSS and target performance must be checked before promotion.

```sh
rustc --edition=2021 -O -C lto=fat -C codegen-units=1 -C panic=abort -C target-cpu=x86-64-v3 experiments/b-sparse-rebased/baseline.rs -o /tmp/b-sparse-base
rustc --edition=2021 -O -C lto=fat -C codegen-units=1 -C panic=abort -C target-cpu=x86-64-v3 experiments/b-sparse-rebased/threshold512.rs -o /tmp/b-sparse-cand
python3 experiments/b-sparse-rebased/run-independent.py
python3 experiments/b-sparse-rebased/make-test.py --force-sparse --zero-short-hash --output /tmp/b-sparse-forced.rs
rustc --edition=2021 -O -C overflow-checks=yes -C target-cpu=x86-64-v3 /tmp/b-sparse-forced.rs -o /tmp/b-sparse-forced
B_RUST_BINARY=/tmp/b-sparse-forced python3 experiments/b-bounded-fuzz.py "$PWD/experiments/b-rust-positional-adapter.py"
B_RUST_BINARY=/tmp/b-sparse-forced python3 experiments/b-boolean-clauses/algebra.py "$PWD/experiments/b-rust-positional-adapter.py"
python3 experiments/b-sparse-rebased/make-test.py --workers 1 --trace --output /tmp/b-sparse-trace.rs
rustc --edition=2021 -O -C overflow-checks=yes -C target-cpu=x86-64-v3 /tmp/b-sparse-trace.rs -o /tmp/b-sparse-trace
python3 experiments/b-sparse-postings/cutoff-review.py /tmp/b-sparse-trace /tmp/b-sparse-trace
rustc --edition=2021 -O -C overflow-checks=yes -C target-cpu=x86-64-v3 experiments/b-avx2-token/classifier-property.rs -o /tmp/b-classifier
/tmp/b-classifier
python3 experiments/b-avx2-token/alignment.py /tmp/b-sparse-cand official/reference/b_index.py
export B_RUST_BINARY=/tmp/b-sparse-cand
python3 experiments/b-bounded-fuzz.py "$PWD/experiments/b-rust-positional-adapter.py"
python3 experiments/b-bounded-shards.py "$PWD/experiments/b-rust-positional-adapter.py"
python3 experiments/b-bounded-boundary.py "$PWD/experiments/b-rust-positional-adapter.py"
python3 experiments/b-bounded-duplicates.py "$PWD/experiments/b-rust-positional-adapter.py"
python3 experiments/b-boolean-clauses/algebra.py "$PWD/experiments/b-rust-positional-adapter.py"
python3 experiments/b-rust-lengthhash/compare.py --baseline /tmp/b-sparse-base --candidate /tmp/b-sparse-cand --data /path/to/full-b --runs 15 --report /tmp/b-sparse-x86.json
```

The comparison script alternates randomized order and checks every output hash. Independently verify actual page-guard coverage and cgroup peak memory on the target. Keep baseline if target results do not show a repeatable speed improvement.

## Dot VM comparison against dynamic global B

The parent-run shared x86 VM compared sparse-512 (based on the older per-chunk implementation) with the current dynamic global-query candidate: paired wall time was 0.8–2.5% lower, but a four-way rotation showed only 0.34% lower, with slightly higher native RSS. On synthetic skew it was 9.6–17% faster. Across the comparison 192 full hashes, 16 alternate references, 48 skew cases and collision/duplicate/AVX2 tests passed. This was not a tested sparse-plus-dynamic combination; native VM results are not official scoring-box or cgroup evidence. The candidate remains isolated.
