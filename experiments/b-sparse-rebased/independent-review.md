# Independent review of sparse-512 branch

Reviewed `threshold512.rs` SHA-256 `c2d41e1e001ad67d3b0a808ca65b3207fc528c34ba80bf308597d60cc5b361c4` against baseline `322cc95ee08cf6d4abc5e1b52240753f66c7eaf89ab669cb6d72b0a8487dc458`. No semantic defect found in the changed path under the official document and query bounds.

Each posting list is sorted and unique because document IDs arrive in order and the indexing stamp emits each term at most once per document. The merge loop preserves sorted uniqueness. For OR it emits the union; AND emits only equality; NOT emits the left difference. The leading BOOL token is handled as OR against an empty set. Each operation is applied in input order. Empty, repeated or overlapping postings do not alter those identities. Every intermediate sparse set has size no larger than the sum of its input posting lengths, so the threshold of 512 bounds it to 512 IDs; its two reusable vectors retain at most the largest observed sparse result. Result count, ID sum and first ten are computed directly in order. Phrases and the original bitmap cap/fallback are untouched.

With overflow checks enabled, an exact-source one-worker build passed the existing 5,379-query independent reference fixture with total posting lengths around 511/512/513, mixed OR/AND/NOT and duplicates. The normal threshold, a test-only always-sparse build, and a test-only always-bitmap build each passed 5,364 expressions across all 64 membership assignments. The exact candidate also passed 310,536 official-reference query comparisons across workers 1/2/3/7/12/32, zero/eight-byte bitmap caps and document counts 0/1/2/7/8/63/64/65/129, including mixed empty/revived states. Tests use native ARM and do not validate Linux AVX2, cgroup memory, all possible inputs or x86 performance. No selected source was changed and no Mac Docker was used.

Run all independent checks from the repository root:

```sh
python3 experiments/b-sparse-rebased/run-independent.py
```

The wrapper checks both source SHA-256 digests, compiles temporary baseline and candidate variants with overflow checks, then runs the cutoff, exhaustive algebra, and worker/cap reference suites. The forced sparse and forced bitmap variants are test scaffolding, not submission candidates. Archive dependencies are `experiments/b-sparse-postings/cutoff-review.py`, `experiments/b-boolean-clauses/algebra.py`, `experiments/b-rust-positional-adapter.py`, `experiments/b-sparse-rebased/caps-review.py`, and `official/reference/b_index.py`.
