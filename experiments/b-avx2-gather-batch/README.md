# B four-lane gather experiment

Isolated experiment only; **not selected or submitted**. Baseline is the selected
B source with SHA-256 `7d371fe84ce9f0fd9d3c7e6fdf02b6b37e0f1440319c654161b990cf27bb8bf3`.
Candidate SHA-256 is `ebfb413f8dc95cf9071ab9d8dd8e0d3deb0d2f303fb924d68f3c0bf1caae4ad8`.
For each document, batch four tokens and gather the first short-hash slot and
key word; collisions use the exact existing scalar probe. Long words and final
partial batches also use the existing path. MISS lanes are sanitized before
the second gather; empty-key tables and excessive signed offsets avoid it.

Independent static review found no concrete pointer or correctness defect under
the existing Plan invariants. Local ARM testing executes the scalar batch
fallback, **not the x86 gather**: nine randomized paired full-seed medians were
0.27176 s baseline and 0.27469 s candidate, CPU 1.5672 vs 1.6536 s; all 20
executions matched the expected hash. Forty mixed reference corpora passed.
Normal and forced-zero-hash property suites passed, including protected token
pages and 493,216 exhaustive/random token-boundary documents. Separate Windows
x86 cross-compilation generated `vpgatherdd` and `vpgatherdq`; it did not run
the instructions. No x86 correctness or speed claim can be made yet.

On a disposable Linux x86-64 host with the official full seed available, from
the repository root, first run the test preflight. It checks v3 CPU flags before
compiling or executing, requires the actual AVX2 guard-page test to run, checks
MISS/non-short key gathers beside protected pages, exercises collision fallback,
and compares batched tokenization with the scalar oracle:

```
python3 experiments/b-avx2-gather-batch/run-property.py --x86-v3
rustc --edition=2021 -O -C target-cpu=x86-64-v3 experiments/b-avx2-gather-batch/baseline.rs -o /tmp/b-gather-baseline
rustc --edition=2021 -O -C target-cpu=x86-64-v3 experiments/b-avx2-gather-batch/candidate.rs -o /tmp/b-gather-candidate
B_RUST_BINARY=/tmp/b-gather-candidate python3 experiments/b-bounded-fuzz.py "$PWD/experiments/b-rust-positional-adapter.py"
python3 experiments/b-rust-lengthhash/compare.py --baseline /tmp/b-gather-baseline --candidate /tmp/b-gather-candidate --data /path/to/b/full --runs 15 --report /tmp/b-gather-x86.json
```

Reference test needs `official/reference/b_index.py`. Comparator validates every
full output hash and uses randomized paired order; VM timing is non-official and
must not be conflated with official cgroup scoring. Run target-specific guarded
tests and benchmark before considering promotion. The AVX2 branch is only
enabled at compile time with `target_feature=avx2`; generic builds use scalar.
