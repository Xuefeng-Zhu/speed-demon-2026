# B four-way exact short-token groups (experimental)

This replaces only the ≤8-byte lookup table: each 64-byte-aligned group holds four full 64-bit exact keys and their original IDs. A generated x86-64-v3 build uses an AVX2 four-lane equality comparison; portable builds use a scalar comparison. Groups fill before probing the next, so absence can be returned at the first group containing an empty key. A zero key is reserved for empty; legal tokens contain nonzero ASCII bytes. Group capacity is at least twice the short-term count. Long tokens, document ordering, phrase deduplication, bitmap bounds and Boolean evaluation are unchanged.

Baseline source SHA-256 `322cc95ee08cf6d4abc5e1b52240753f66c7eaf89ab669cb6d72b0a8487dc458`; candidate `48d573369af70b6e63f6ee736d560d79cce1533d66238fe06a70f3b3b750cfb9`. On shared native macOS ARM (scalar fallback), 11 randomized warmed full-seed pairs measured 0.257071 vs 0.255970 seconds and 1.541628 vs 1.576293 CPU seconds; a 15-pair repeat measured 0.252399 vs 0.261301 seconds and 1.550203 vs 1.581058 CPU seconds. All 56 full output hashes, including warmups, passed. Native process results are noisy, not x86, official scoring, or cgroup evidence.

An independent static review found no alignment or collision defect. Independent exact-source tests checked 317,140 lookups, empty/partial/full groups, capacity growth, 32 input alignments, present/absent terms and short/long boundaries, repeated with all short hashes forced to zero. The candidate additionally passed a 100,000-key exact-source property test (5,000 forced-collision keys), 40 mixed-reference corpora, 40 forced-collision-reference corpora with overflow checks, 250,000-document/19,000 duplicate-phrase stress, 3,072 tokenizer alignment documents, distributed top ten and >1 MiB line tests. A temporary Windows x86-64-v3 metadata build typechecked the AVX2 intrinsics with the Linux file-descriptor call stubbed. **Actual Linux/x86 AVX2 and protected-page tests have not yet run.** No Mac Docker was used.

## Required target validation

Run from the archive root on AVX2 Linux x86-64, with no competing benchmark and separately generated official full seed-1 data. `run-property.py --x86-v3` refuses non-Linux/x86 and fails unless its AVX2 protected-page test actually runs. It tests group loads at both boundaries of an accessible memory page flanked by PROT_NONE pages, normal and all-short-hashes-equal cases, and randomized lane masks.

```sh
rustc --edition=2021 -O -C lto=fat -C codegen-units=1 -C panic=abort -C target-cpu=x86-64-v3 experiments/b-group4-short/baseline.rs -o /tmp/b-group4-base
rustc --edition=2021 -O -C lto=fat -C codegen-units=1 -C panic=abort -C target-cpu=x86-64-v3 experiments/b-group4-short/candidate.rs -o /tmp/b-group4-candidate
python3 experiments/b-group4-short/run-property.py --x86-v3
python3 experiments/b-group4-short/make-forced.py /tmp/b-group4-forced.rs
rustc --edition=2021 -O -C overflow-checks=yes -C target-cpu=x86-64-v3 /tmp/b-group4-forced.rs -o /tmp/b-group4-forced
B_RUST_BINARY=/tmp/b-group4-forced python3 experiments/b-bounded-fuzz.py "$PWD/experiments/b-rust-positional-adapter.py"
python3 experiments/b-avx2-token/alignment.py /tmp/b-group4-candidate official/reference/b_index.py
rustc --edition=2021 -O -C overflow-checks=yes -C target-cpu=x86-64-v3 experiments/b-avx2-token/classifier-property.rs -o /tmp/b-classifier-test && /tmp/b-classifier-test
export B_RUST_BINARY=/tmp/b-group4-candidate
python3 experiments/b-bounded-fuzz.py "$PWD/experiments/b-rust-positional-adapter.py"
python3 experiments/b-bounded-shards.py "$PWD/experiments/b-rust-positional-adapter.py"
python3 experiments/b-bounded-boundary.py "$PWD/experiments/b-rust-positional-adapter.py"
python3 experiments/b-bounded-duplicates.py "$PWD/experiments/b-rust-positional-adapter.py"
python3 experiments/b-rust-lengthhash/compare.py --baseline /tmp/b-group4-base --candidate /tmp/b-group4-candidate --data /path/to/full-b --runs 15 --report /tmp/b-group4-x86.json
```

The test property includes forced short-hash collisions but the full-program forced-hash reference corpus should also be run; use `make-forced.py` to generate that candidate. Do not select without repeated x86 timings, correctness and official sandbox and practice results. No datasets or cached answers are bundled.

## Dot VM x86 comparison

The parent-run native x86 paired batches reported 1.9–3.0% lower wall time than the exact baseline. Across this, C parser and D mmap packages, 164 full hashes, 24 alternate comparisons, Linux/AVX2 guard-page, collision, boundary and graph-oracle checks passed. This remains an isolated candidate pending a separately controlled official comparison.
