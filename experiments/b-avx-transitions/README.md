# Track B direct short lookup and transition-mask scan

Two independent, unselected candidates use the exact selected B baseline SHA-256 `322cc95ee08cf6d4abc5e1b52240753f66c7eaf89ab669cb6d72b0a8487dc458`. They change different hot paths; benchmark them individually before considering a combined variant. The archives have source, tests, official reference/generator/spec/license, and no datasets or credentials.

## PEXT direct short lookup

Candidate `experiments/b-pext-direct/candidate.rs`, SHA-256 `b8325777e95bf96185a6b525f6e3cb25f23604125c1823c3a0cfb77dc528eabe`, maps every valid lowercase alphanumeric token of length 1–4 injectively to a four-digit, 24-bit direct-table index. The actual direct path is compiled only when `target_arch=x86_64` and BMI2 is a compile-time target feature; all other normal builds use the original table. It stores ID+1 and uses zero for MISS. No corpus values or answers are built in. Long terms, Boolean and phrase semantics, phrase-summary bounds and bitmap cap remain unchanged.

The table reserves **64 MiB** virtual address space; actual charged memory depends on the Linux allocator and page accesses and must be measured. The portable arithmetic emulation used only for testing was slower on shared ARM: 11-pair median 0.41915 vs 0.38021 s wall and 1.66254 vs 1.50661 s CPU. This is not actual BMI2/PEXT, x86 or official evidence. All 24 full-seed hashes passed. An independent review exhaustively checked 1,727,604 valid 1–4-byte encodings, uppercase equivalents, and 489,077 Plan lookup/boundary cases; exact-source property tests repeated all legal encodings with normal and forced short-hash collisions. Portable emulation passed 40 randomized reference corpora, 40 more with all short hashes forced equal, top-ten, long-line, 3,072 alignment documents and 250k-document/19k-duplicate stress. The ordinary non-BMI fallback passed the full hash. An x86-v3 Windows helper assembly contains PEXT; actual Linux BMI2 and guarded-page tests are unexecuted.

## Transition-mask scan

Candidate `experiments/b-avx-transitions/candidate.rs`, SHA-256 `820978f733530d4a477cc5c1bb4947748b1d03cfe9cafcb72c69de5f25b9c0b5`, changes only how the already-computed 32-bit alphanumeric mask is decoded: start/end transition masks replace dynamic shifts/trailing-ones. Open tokens are carried across blocks. The guarded classifier, key equality, dictionary, phrase and Boolean logic remain unchanged.

Two native shared-ARM scalar-fallback comparisons measured candidate/baseline wall 0.26634/0.27245 s and 0.26095/0.26028 s; CPU 1.50304/1.56048 and 1.52770/1.58638 s. All 56 full hashes including warmups passed. Wall time is tied/noisy; CPU was about 3.7% lower. This is not x86 or official evidence. Independent exact-source tests passed 493,216 exhaustive-mask and random 32-byte-boundary documents, and the candidate passed 40 randomized reference corpora, top-ten, long-line, 3,072 alignment documents and 250k-document/19k-duplicate stress. Actual x86 AVX2 scan execution remains untested.

## Serialized Linux x86-64-v3 validation

Run on the AVX2/BMI2 Linux target without concurrent benchmarks; generate full seed-1 inputs independently. Both property scripts require actual target features and refuse to claim success if guarded tests were compiled out. Measure native process RSS and, separately, cgroup peak for the 64 MiB virtual direct table.

```sh
rustc --edition=2021 -O -C lto=fat -C codegen-units=1 -C panic=abort -C target-cpu=x86-64-v3 experiments/b-avx-transitions/baseline.rs -o /tmp/b-base
rustc --edition=2021 -O -C lto=fat -C codegen-units=1 -C panic=abort -C target-cpu=x86-64-v3 experiments/b-avx-transitions/candidate.rs -o /tmp/b-transition
rustc --edition=2021 -O -C lto=fat -C codegen-units=1 -C panic=abort -C target-cpu=x86-64-v3 experiments/b-pext-direct/candidate.rs -o /tmp/b-pext
python3 experiments/b-avx-transitions/run-property.py --x86-v3
python3 experiments/b-pext-direct/run-property.py --x86-v3
rustc --edition=2021 -O -C overflow-checks=yes -C target-cpu=x86-64-v3 experiments/b-avx2-token/classifier-property.rs -o /tmp/b-classifier && /tmp/b-classifier
python3 experiments/b-pext-direct/make-forced.py /tmp/b-pext-forced.rs
rustc --edition=2021 -O -C overflow-checks=yes -C target-cpu=x86-64-v3 /tmp/b-pext-forced.rs -o /tmp/b-pext-forced
B_RUST_BINARY=/tmp/b-pext-forced python3 experiments/b-bounded-fuzz.py "$PWD/experiments/b-rust-positional-adapter.py"
for bin in /tmp/b-transition /tmp/b-pext; do
  python3 experiments/b-avx2-token/alignment.py "$bin" official/reference/b_index.py
  B_RUST_BINARY="$bin" python3 experiments/b-bounded-fuzz.py "$PWD/experiments/b-rust-positional-adapter.py"
  B_RUST_BINARY="$bin" python3 experiments/b-bounded-shards.py "$PWD/experiments/b-rust-positional-adapter.py"
  B_RUST_BINARY="$bin" python3 experiments/b-bounded-boundary.py "$PWD/experiments/b-rust-positional-adapter.py"
  B_RUST_BINARY="$bin" python3 experiments/b-bounded-duplicates.py "$PWD/experiments/b-rust-positional-adapter.py"
done
python3 experiments/b-rust-lengthhash/compare.py --baseline /tmp/b-base --candidate /tmp/b-transition --data /path/to/full-b --runs 15 --report /tmp/b-transition-x86.json
python3 experiments/b-rust-lengthhash/compare.py --baseline /tmp/b-base --candidate /tmp/b-pext --data /path/to/full-b --runs 15 --report /tmp/b-pext-x86.json
```

Use the official sandbox and board for actual scoring. Do not select a candidate from ARM data alone.
