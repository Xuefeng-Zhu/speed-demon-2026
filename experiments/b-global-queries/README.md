# Track B global-query parallelism with shared dense cache (experimental)

Against exact selected baseline SHA-256 `322cc95ee08cf6d4abc5e1b52240753f66c7eaf89ab669cb6d72b0a8487dc458`, candidate `shared.rs` SHA-256 `58ea98f48a322c3af1837a1dd1a19767250232e4c3f690e298c7e9ac95c83dfe` indexes the corpus in parallel into exact chunk-local CSR postings and bounded phrase summaries, then assigns contiguous query ranges to workers. Boolean evaluation uses global document bitmaps; phrase summaries merge in input-chunk order. Dense global bitmaps are constructed once per term with `OnceLock` and a shared atomic **64 MiB payload cap**, and exact postings are used if the cap cannot be reserved. Cache metadata, scratch buffers and CSR arrays are additional memory. Duplicate phrases retain bounded summaries, and no corpus values or answers are precomputed.

Two randomized warmed native shared-Mac ARM batches gave candidate/baseline medians: 11 pairs 0.256681/0.261749 s wall, 1.540983/1.584682 s CPU and 516,243,456/527,630,336 B median process RSS; 15 pairs 0.271205/0.280088 s wall, 1.540346/1.591684 s CPU and 515,522,560/527,712,256 B RSS. All 56 hashes including warmups matched. The earlier version with separate global cache per query worker (`candidate.rs`, not selected) had higher CPU and about 45 MiB more native RSS; `report.json` and `repeat.json` preserve that negative result. Shared-host ARM scalar tokenizer results are noisy and are not x86, official wall or parent-cgroup peak measurements.

Independent review found no defect in shared publication, atomic cap, fallback, posting offsets, phrase merge or query order; see `independent-review.md`. Exact-source tests passed 323,200 byte-equal reference queries across 1/2/3/7/12/32 workers, document counts around 64-bit boundaries, and cache caps zero/eight bytes. Two separate concurrent cache tests cover 16/32 workers, nonaligned offsets, exact quota exhaustion, concurrent initialization, publication and zero/eight-byte fallback. It also passed 40 mixed references, 5,364 Boolean expressions × 64 membership assignments, top-ten/overlapping phrases, >1 MiB lines, 250k-document/19k-duplicate stress and 3,072 token-alignment documents. These tests do not prove every thread interleaving or execute Linux x86 AVX2. No Mac Docker was used. The candidate is unselected pending target measurements.

## Required serialized Linux x86-64-v3 tests

From archive root on an AVX2-capable Linux x86 VM, with separately generated full seed-1 data and no concurrent benchmarks:

```sh
for n in baseline shared; do rustc --edition=2021 -O -C lto=fat -C codegen-units=1 -C panic=abort -C target-cpu=x86-64-v3 "experiments/b-global-queries/$n.rs" -o "/tmp/b-global-$n"; done
python3 experiments/b-global-queries/run-cache-test.py --x86-v3
python3 experiments/b-global-queries/independent-review.py
rustc --edition=2021 -O -C overflow-checks=yes -C target-cpu=x86-64-v3 experiments/b-avx2-token/classifier-property.rs -o /tmp/b-classifier && /tmp/b-classifier
python3 experiments/b-avx2-token/alignment.py /tmp/b-global-shared official/reference/b_index.py
export B_RUST_BINARY=/tmp/b-global-shared
python3 experiments/b-bounded-fuzz.py "$PWD/experiments/b-rust-positional-adapter.py"
python3 experiments/b-bounded-shards.py "$PWD/experiments/b-rust-positional-adapter.py"
python3 experiments/b-bounded-boundary.py "$PWD/experiments/b-rust-positional-adapter.py"
python3 experiments/b-bounded-duplicates.py "$PWD/experiments/b-rust-positional-adapter.py"
python3 experiments/b-boolean-clauses/algebra.py "$PWD/experiments/b-rust-positional-adapter.py"
python3 experiments/b-rust-lengthhash/compare.py --baseline /tmp/b-global-baseline --candidate /tmp/b-global-shared --data /path/to/full-b --runs 15 --report /tmp/b-global-x86.json
```

The benchmark checks the full hash after every execution and reports native process RSS, not official cgroup peak. Compare repeated wall/CPU, peak cgroup memory, source size and actual practice-box behavior before considering selection. Contiguous query blocks could be imbalanced if query order is skewed. No dataset, credentials or cached answers are included.
