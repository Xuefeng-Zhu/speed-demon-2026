# Fused B token and newline scan (experimental)

The candidate classifies tokens and newlines in the same 32-byte block, instead
of calling `memchr` to find each line end before classifying the line. Loads are
guarded by the remaining whole-line chunk, and a newline mask limits emitted
tokens to the current document. Full-byte key equality, bounded phrase summaries,
bitmap cap and query logic are unchanged. Baseline is selected B source SHA-256
`322cc95ee08cf6d4abc5e1b52240753f66c7eaf89ab669cb6d72b0a8487dc458`;
candidate SHA-256 is `2128253e46ac18739ecfaa020ffaec6fa7acd1699f4aeaa764ea76a790dfe9ca`.

Native ARM scalar-path testing passed all full seed-1 hashes in warmup plus nine
randomized pairs; median candidate wall was 0.274497 s versus 0.264692 s
baseline, CPU 1.625668 versus 1.573197 s. This is a negative, noisy screen,
not a prediction of x86 AVX2 speed. It passed 40 randomized references, >1 MiB
read boundaries, 3,072 alignment documents, an exhaustive 47,988 tiny-token
fixture, and 250k-document/19k-duplicate-phrase stress. Independent review
found no boundary defect and passed 20 corpora across 1/2/3/7/12/32 workers
against the official reference with overflow checks (`independent.py`).

**The actual x86 AVX2 path has not been executed.** Before considering the
candidate, run `python3 experiments/b-fused-newline/verify-classifier.py`, then
compile `classifier-property.rs` with AVX2 enabled and run it on x86 Linux;
it checks byte/lane/fill, random vectors and page guards. Also rerun
`python3 experiments/b-fused-newline/independent.py
experiments/b-fused-newline/candidate.rs official/reference/b_index.py`, the
existing B fuzz, shard, boundary, duplicate and AVX2 alignment fixtures, and a
serialized full-hash paired comparison against `baseline.rs`. No Docker was used.
