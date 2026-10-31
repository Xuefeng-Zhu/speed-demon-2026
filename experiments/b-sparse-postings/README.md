# B sparse-postings Boolean path (experimental)

`baseline.rs` is the exact selected short-token implementation (SHA-256 `d0f0d79f3f646275d2e33ef34659eba5bca56fb2bb16504025f10a800e88cc49`). Each threshold candidate computes the total length of the Boolean query's chunk-local postings. If this total does not exceed the threshold, it evaluates strict left-to-right AND/OR/NOT by merging sorted posting vectors, then directly summarizes the final sorted IDs. Otherwise it uses the unchanged bitmap evaluator. Scratch vectors are reused within each worker; phrase handling, bounded phrase summaries and bitmap cap are unchanged. This is not selected code.

The candidate with threshold 128 matched every published full-seed hash in a 7-pair native ARM Mac comparison; candidate/baseline median wall was 0.29147/0.29938 s, CPU 1.6451/1.6702 s. Three subsequent 5-pair screens gave threshold 32 0.42528/0.37829 s, threshold 512 0.38733/0.42371 s and threshold 2048 0.38382/0.41043 s. Every output hash matched. Raw samples are in `report*.json`. These screens were run sequentially on a shared host, so comparisons across thresholds are not controlled; native ARM uses the scalar tokenizer, RSS is process memory rather than cgroup peak, and performance on x86 remains unknown.

The subsequent dot VM x86 screen compared these older sparse variants with the current dense-summary implementation: current median was 0.28895 s and the best sparse-512 variant 0.30039 s, about 4% slower. The sparse candidate did not incorporate the dense-summary optimization, so this is not an isolated estimate of the sparse path on top of current code. Across the C/B campaign 112 full hashes, 32 alternates and stress checks passed. Exact individual samples were not supplied; no sparse variant was promoted.

Thresholds 128 and 512 each passed the 40-corpus mixed official-reference fuzz, distributed top-ten/duplicate/overlap and >1 MiB boundary fixtures. Threshold 512 also passed the 250,000-document / 19,000-duplicate-phrase / 31,000-Boolean-query stress. `forced.rs` changes the threshold to `usize::MAX` solely to exercise sorted-set branches; an overflow-check-enabled build passed the same 40 reference corpora and shard fixture. It is not a candidate for full input or scoring. Independent review found no semantic, ordering, overflow or race defect under published bounds; an overflow-checked forced-one-worker test checked 5,379 queries including thresholds 511/512/513 and all AND/OR/NOT sequences (`cutoff-review.py`). X86 speed and cgroup measurement remain required before selection.

From the repository root, compile candidates with the same release/ISA flags; compare generated full seed-1 data with:

```
python3 experiments/b-rust-lengthhash/compare.py --baseline /path/to/base --candidate /path/to/candidate --data /path/to/full-b --runs 7 --report /tmp/b-sparse-result.json
B_RUST_BINARY=/path/to/candidate python3 experiments/b-bounded-fuzz.py "$PWD/experiments/b-rust-positional-adapter.py"
B_RUST_BINARY=/path/to/candidate python3 experiments/b-bounded-shards.py "$PWD/experiments/b-rust-positional-adapter.py"
```

No Mac Docker was used. No generated corpus or precomputed answer is included; supplied hashes are used only for output verification.
