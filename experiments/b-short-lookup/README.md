# Speed Demon B: exact short-token lookup experiment

This archive compares the exact selected AVX2 B at commit b07315c (baseline.rs SHA-256 c8ccf63c9c423986ff51bcb8c2f40a41288ebcc26d54e36bc43ee9005ed99518) against candidate.rs SHA-256 d0f0d79f3f646275d2e33ef34659eba5bca56fb2bb16504025f10a800e88cc49. Candidate builds an immutable, at-most-half-full exact table for tokens of up to eight bytes; longer terms retain original exact lookup. Zero padding is unambiguous for legal nonzero ASCII tokens. Bounded phrase summaries and bitmap cap are unchanged. No cached answers or datasets are included.

Native shared-Mac ARM scalar-fallback seven-pair medians were 0.3134 s candidate vs 0.3262 s baseline, CPU 1.748 vs 1.824 s; all full hashes passed. These are noisy and DO NOT exercise the AVX2 path. Candidate passed 40 mixed reference corpora, duplicate-phrase stress (250k docs/19k phrases), max 338k query terms, distributed top-ten and >1 MiB boundaries. Independent overflow-check property passed 100k generated present/absent terms and 5k with all short hashes forced equal. Deterministic hashing is not a general hash-flooding guarantee.

On AVX2 Linux x86-64, from archive root, run these correctness checks before timing; use Python 3.13+ and Rust with x86-64-v3 support:

```
rustc --edition=2021 -O -C lto=fat -C codegen-units=1 -C panic=abort -C target-cpu=x86-64-v3 baseline.rs -o /tmp/b-short-base
rustc --edition=2021 -O -C lto=fat -C codegen-units=1 -C panic=abort -C target-cpu=x86-64-v3 candidate.rs -o /tmp/b-short-candidate
python3 verify-classifier.py
rustc --edition=2021 -O -C overflow-checks=yes -C target-cpu=x86-64-v3 classifier-property.rs -o /tmp/b-avx-property && /tmp/b-avx-property
rustc --edition=2021 --test -C opt-level=2 -C overflow-checks=yes -C target-cpu=x86-64-v3 candidate-property.rs -o /tmp/b-short-property && /tmp/b-short-property
rustc --edition=2021 --test -C opt-level=2 -C overflow-checks=yes -C target-cpu=x86-64-v3 forced-property.rs -o /tmp/b-short-forced && /tmp/b-short-forced
python3 independent-review.py /tmp/b-short-base /tmp/b-short-candidate
python3 alignment.py /tmp/b-short-candidate official/reference/b_index.py
python3 forced-workers.py
export B_RUST_BINARY=/tmp/b-short-candidate
python3 tests/b-bounded-fuzz.py "$PWD/tests/b-rust-positional-adapter.py"
python3 tests/b-bounded-shards.py "$PWD/tests/b-rust-positional-adapter.py"
python3 tests/b-bounded-boundary.py "$PWD/tests/b-rust-positional-adapter.py"
python3 tests/b-bounded-duplicates.py "$PWD/tests/b-rust-positional-adapter.py"
python3 experiments/b-packed-nonlinear-review/max_vocabulary.py "$PWD/tests/b-rust-positional-adapter.py"
python3 compare.py --baseline /tmp/b-short-base --candidate /tmp/b-short-candidate --data /path/to/separately/generated/full-b --runs 9 --report /tmp/b-short-x86.json
```

The final comparator alternates randomized order, validates each published full hash, and records native process wall/CPU/RSS. It does not measure cgroup peak. Avoid concurrent VM benchmarks. Compare official time, peak memory and source score before promotion; Rust x86 AVX2 guard-page checks are essential. No Mac Docker was used.

Library transfer: `libfile_76775e15eeb481918fb9fc38c9098220`, SHA-256 `1d960d22eefcd4635da80728abb54777a1d6816fe436fd0dccde70ac936e2b72`. The full transfer archive contains the scripts and official reference tree mentioned above; these paths are archive-relative.
