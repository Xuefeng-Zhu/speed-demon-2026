# Track B CRC32C short-word hash (experimental)

The exact restored baseline is `baseline.rs`, SHA-256 `322cc95ee08cf6d4abc5e1b52240753f66c7eaf89ab669cb6d72b0a8487dc458`. Candidate `candidate.rs`, SHA-256 `05db9418fcacf0662482eea4a29f338ef21454befee8035417455008fa16737b`, tries a hardware CRC32C hash for alphanumeric tokens up to eight bytes only when the compile target guarantees x86 SSE4.2. Keys are always compared exactly. A query-derived trial table is rejected and rebuilt using the original hash if any insertion needs more than 32 extra probes or any cyclic occupied run exceeds 64; the latter also bounds unsuccessful lookup scans. Non-SSE4.2 normal builds use only the original hash. The test-only software emulation and forced-collision flags are not enabled in production. Phrase and Boolean logic, bitmap cap and all long-token handling are unchanged.

A read-only simulation of the full-seed queries and first 512 KiB corpus gave CRC versus baseline 1.17799 versus 1.18310 average short lookup probes, with max occupied runs 32 versus 20. This is diagnostic, not timing. The portable CRC emulation gave five warmed ARM pairs candidate/baseline 0.316976/0.260113 s wall and 1.857034/1.573334 s CPU; software CRC takes eight table steps and is not representative of an x86 CRC32 instruction. All 12 full hashes passed. The x86-v3 Windows cross-assembly (with Linux file descriptor temporarily stubbed) contained `crc32q`, but **the real Linux instruction path, scoring-box speed and cgroup memory are untested**. No performance win is claimed.

On ARM emulation, the full seed matched and reported CRC mode active; generic fallback also matched. Exact-source properties checked 300,000 pseudorandom CRCs against an independent bitwise CRC32C reference and checked full present/absent key equality. A forced-constant-CRC case proved insertion guard fallback; a constructed 65-slot cyclic cluster straddling the table edge used zero insertion displacements and proved cluster guard fallback. Normal and forced-constant emulation each passed 40 randomized reference corpora; normal also passed 90 independent corpora, distributed-top-ten, long-line, 250k-document/19k-duplicate-phrase stress and 3,072 alignment documents. Independent review found no correctness defect; exact-source tests also covered the accepted and rejected 32/33 displacement and 64/65 cyclic-run thresholds, empty tables and long-only terms. This work is experimental and has not been selected. No Mac Docker was used.

## Linux x86-64-v3 tests

Run from this archive's root on an SSE4.2/AVX2-capable Linux x86 host, serialized with other VM work, using a separately generated full seed-1 dataset. The exact-source property script requires the hardware/guard tests to run and checks CRC against bitwise reference, cyclic-wrap/insertion guards, and short lookups adjacent to inaccessible pages.

```sh
rustc --edition=2021 -O -C lto=fat -C codegen-units=1 -C panic=abort -C target-cpu=x86-64-v3 experiments/b-crc-short/baseline.rs -o /tmp/b-crc-base
rustc --edition=2021 -O -C lto=fat -C codegen-units=1 -C panic=abort -C target-cpu=x86-64-v3 experiments/b-crc-short/candidate.rs -o /tmp/b-crc-candidate
rustc --edition=2021 -O -C overflow-checks=yes -C target-cpu=x86-64-v3 --cfg b_crc_forced_collision experiments/b-crc-short/candidate.rs -o /tmp/b-crc-forced
python3 experiments/b-crc-short/run-property.py --x86-v3
rustc --edition=2021 -O -C overflow-checks=yes -C target-cpu=x86-64-v3 experiments/b-avx2-token/classifier-property.rs -o /tmp/b-classifier && /tmp/b-classifier
python3 experiments/b-avx2-token/alignment.py /tmp/b-crc-candidate official/reference/b_index.py
python3 experiments/b-short-lookup/independent-review.py /tmp/b-crc-candidate
B_RUST_BINARY=/tmp/b-crc-forced python3 experiments/b-bounded-fuzz.py "$PWD/experiments/b-rust-positional-adapter.py"
export B_RUST_BINARY=/tmp/b-crc-candidate
python3 experiments/b-bounded-fuzz.py "$PWD/experiments/b-rust-positional-adapter.py"
python3 experiments/b-bounded-shards.py "$PWD/experiments/b-rust-positional-adapter.py"
python3 experiments/b-bounded-boundary.py "$PWD/experiments/b-rust-positional-adapter.py"
python3 experiments/b-bounded-duplicates.py "$PWD/experiments/b-rust-positional-adapter.py"
python3 experiments/b-crc-short/probe-sample.py --data /path/to/full-b
python3 experiments/b-rust-lengthhash/compare.py --baseline /tmp/b-crc-base --candidate /tmp/b-crc-candidate --data /path/to/full-b --runs 15 --report /tmp/b-crc-x86.json
```

Review both guard fallbacks and the exact candidate independently, measure actual CPU/wall and memory in repeated paired x86 runs, and require official practice/sandbox results before any selection. This archive contains no datasets, credentials or cached answers.
