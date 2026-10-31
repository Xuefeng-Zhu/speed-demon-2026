# Track B batched lookup and prefetch (experimental)

`baseline.rs` is the exact selected B (SHA-256 `322cc95ee08cf6d4abc5e1b52240753f66c7eaf89ab669cb6d72b0a8487dc458`); `candidate.rs` SHA-256 is `f0606f0148682ab5cdade44acf0d078e165c85d39e86187848f0654fea1f2077`. This changes document token processing: it first collects the current document's byte ranges, then resolves them in order in batches of eight, prefetching the short-table slots and then the corresponding key entries on x86-64. A nonmatching first slot falls back to the original exact linear-probe lookup. Long tokens use the existing exact lookup; tokens over 32 bytes remain MISS. The range vector is cleared after each document and is bounded by that document's token count. Phrase summaries and Boolean query handling are unchanged. x86 `_mm_prefetch` is a hint; non-x86 builds use a no-op. This is not selected code.

On shared macOS ARM (scalar classifier; prefetch is a no-op), nine randomized warmed full-data pairs gave median candidate/baseline wall 0.35043/0.35989 s, CPU 1.7705/1.6347 s. Eleven repeat pairs gave 0.30194/0.27794 s wall, 1.7100/1.5776 s CPU; a compilation overlapped the repeat, and other activity could occur in either batch. All 44 executions matched the published full hash. CPU increased roughly 8% in both batches; wall was inconsistent. This does **not** test x86 AVX2 or prefetch, the official scoring box, or cgroup memory. No claim of an x86 win is made. Raw samples are `report.json` and `repeat.json`. No Mac Docker was used.

Normal candidate passed 40 mixed official-reference fuzz corpora, 90 independent corpora, 3,072 documents covering 32-byte alignments, distributed top-ten/overlapping phrases, six >1 MiB lines, and 250,000-document/19,000 duplicate-phrase stress. With all short hashes forced equal and overflow checks enabled it passed the 40-corpus fuzz suite and the exact-source `run-property.py` batch equality suite. That suite also runs normal hashes and compares batches of 0–65 tokens with individual exact lookup, including 1–37-byte tokens and uppercase. Linux runs additionally check 1–37-byte slices adjacent to protected pages; this **Linux guard test is not yet run**. Existing classifier guard test is included and exact classifier-body identity must be checked on x86. All current correctness runs were ARM scalar; x86 SIMD/prefetch correctness remains to be validated.

For isolated AVX2 Linux x86-64 target testing from this archive's root, generate the official full seed-1 data independently and use Rust x86-64-v3. No datasets, binaries, credentials or cached answers are included:

```sh
rustc --edition=2021 -O -C lto=fat -C codegen-units=1 -C panic=abort -C target-cpu=x86-64-v3 experiments/b-batched-prefetch/baseline.rs -o /tmp/b-batch-base
rustc --edition=2021 -O -C lto=fat -C codegen-units=1 -C panic=abort -C target-cpu=x86-64-v3 experiments/b-batched-prefetch/candidate.rs -o /tmp/b-batch-candidate
python3 experiments/b-batched-prefetch/run-property.py
python3 experiments/b-batched-prefetch/verify-classifier.py
rustc --edition=2021 -O -C overflow-checks=yes -C target-cpu=x86-64-v3 experiments/b-avx2-token/classifier-property.rs -o /tmp/b-classifier-property && /tmp/b-classifier-property
python3 experiments/b-avx2-token/alignment.py /tmp/b-batch-candidate official/reference/b_index.py
python3 experiments/b-short-lookup/independent-review.py /tmp/b-batch-candidate
export B_RUST_BINARY=/tmp/b-batch-candidate
python3 experiments/b-bounded-fuzz.py "$PWD/experiments/b-rust-positional-adapter.py"
python3 experiments/b-bounded-shards.py "$PWD/experiments/b-rust-positional-adapter.py"
python3 experiments/b-bounded-boundary.py "$PWD/experiments/b-rust-positional-adapter.py"
python3 experiments/b-bounded-duplicates.py "$PWD/experiments/b-rust-positional-adapter.py"
python3 experiments/b-rust-lengthhash/compare.py --baseline /tmp/b-batch-base --candidate /tmp/b-batch-candidate --data /path/to/full-b --runs 11 --report /tmp/b-batch-x86.json
```

Run benchmarks serialized with the other dot VM work. Every benchmark execution checks the published full hash. Native process RSS and shared VM wall time are not official cgroup or scoring-box results. Inspect alignment, collision fallback and guard-page checks before any promotion; compare official practice results if x86 shows a meaningful and repeatable speedup.

## Dot VM x86 result

The parent-run native x86 comparison regressed versus the exact baseline, so this candidate was not selected. Across this and four other packages, 272 full hashes, 40 alternate comparisons, AVX2/guard, collision and graph-oracle checks passed. This supersedes the earlier statement that its Linux guard and x86 path had not run.
