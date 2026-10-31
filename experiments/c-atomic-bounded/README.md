# Track C bounded atomic dictionary: target comparison

The commands below apply to the separate Library transfer archive (`libfile_8f60221f8bc481918f5fed30fe39003e`, SHA-256 `fe6036d40ffad85e65aacd4e4098ce6e2b6e5499fc02dae84538decbce565602`). This repository directory retains the same Rust sources and raw reports without the archive's `src/` and `official/` layout.

The baseline is the exact selected CRLF Track C from commit 23ffdfc; source SHA-256 `3e181c76981348a96b48470844ee0f8988847d32164ff935a211024861c86ad4`. The experimental candidate SHA-256 is `dc2681bd0ffdb7faf89e05d0ed413cdf118bcfaa1428fa300b88dfe3ce65320d`. No dataset, binary, credential, or precomputed output is included.

The candidate interns names in a concurrent open-addressed atomic pointer table. Entries have immutable borrowed names and four atomic group-bitset words. Each insert checks at most 16 slots; a name that exhausts those slots uses the exact existing mutex-sharded dictionary. Slots are never removed, so a key routed to fallback cannot later enter the permanently occupied probe window. If more than 256 groups are present, all workers use the old sharded dictionary. Published full data has 240 countries plus unmatched. Candidate is experimental, not selected; a separate independent reviewer found no publication/fallback race but target cgroup and performance remain unknown.

With Rust, Python and separately generated full seed-1 data on x86-64-v3, run serially (no parallel benchmark load):

```sh
rustc --edition=2021 -O -C lto=fat -C codegen-units=1 -C panic=abort -C target-cpu=x86-64-v3 src/baseline.rs -o /tmp/c-atomic-baseline
rustc --edition=2021 -O -C lto=fat -C codegen-units=1 -C panic=abort -C target-cpu=x86-64-v3 src/candidate.rs -o /tmp/c-atomic-candidate
python3 experiments/c-rust-independent.py --source src/candidate.rs --seeds 24
python3 experiments/c-rust-independent.py --source src/forced.rs --seeds 24
python3 experiments/c-rust-independent.py --source src/tiny-forced.rs --seeds 24
python3 experiments/multigroup.py src/candidate.rs official/reference/c_join.py
python3 experiments/multigroup300.py src/candidate.rs official/reference/c_join.py
python3 experiments/compare.py --baseline /tmp/c-atomic-baseline --variant /tmp/c-atomic-candidate --data /path/to/generated-full-c --runs 15 --report /tmp/c-atomic-x86.json
```

`forced.rs` forces all hashes equal, and `tiny-forced.rs` also forces a two-slot table; they are test-only and not for benchmarking. The 300-group fixture exercises the all-sharded fallback and is a robustness extension beyond the official group count. All commands use locally installed compilers and generated data; no network or package installation is needed. The comparator verifies the published full output hash on every run and records elapsed time, CPU and wait4 process RSS. RSS is not official warmed-cgroup peak; benchmark cold/warm behavior and measure official memory separately. Exact output hashes may be used for verification only; implementations compute all results from input.

Local shared Mac ARM evidence: candidate vs baseline nine-pair medians 0.177157 vs 0.239721 s, CPU 0.795193 vs 0.929005 s; independent 15-pair medians 0.148339 vs 0.205770 s, CPU 0.818426 vs 0.961984 s. Ranges overlap heavily due to contention; native RSS is not cgroup. Candidate passed 120 normal and 120 forced-hash reference comparisons, 120 two-slot/constant-hash comparisons, and 240/300-group reference fixtures across six worker counts. This does not establish x86 speed or final scoring.

Two subsequent serialized 15-pair dot VM x86 batches showed the candidate 7.7% and 28.1% slower than baseline, with CPU 30–40% higher and process RSS approximately 1.4% higher. All 64 full hashes, eight alternate references and 360 collision/two-slot plus group-fallback tests passed. Exact individual timings were not supplied here. These native VM results are not official cgroup scores; the CRLF baseline remains selected for speed.
