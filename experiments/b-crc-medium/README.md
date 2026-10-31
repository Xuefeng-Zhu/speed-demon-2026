# B two-word medium-token CRC (experimental)

`baseline.rs` is exact selected CRC B source SHA-256 `05db9418fcacf0662482eea4a29f338ef21454befee8035417455008fa16737b`; `candidate.rs` SHA-256 `1b3a1573714a9827df5947d9f6bfb107d109aee3aecd976b7b83b2e0494c1023`. This isolated candidate adds an optional query-derived 9–16-byte term table. It packs the token in two exact zero-padded u64 words, chains CRC32C over both when the target guarantees x86 SSE4.2, then compares both original words. The trial table is accepted only if insertion displacement never exceeds 32 and the longest cyclic occupied run never exceeds 64; otherwise it uses the original generic exact lookup. Short tokens and tokens over 16 bytes retain the baseline paths. On targets without SSE4.2, the baseline lookup remains in use. Phrase summaries, bitmap cap, tokenization and Boolean logic are unchanged.

In the first 1 MiB of full seed-1 corpus (document IDs excluded), 30,062/150,183 text tokens had lengths 9–16. An instrumented portable run activated the query-derived medium table with 26,344 keys in 65,536 slots and matched the full output hash. This is workload characterization, not a target timing.

On shared native ARM, software CRC emulation required 16 lookup steps per medium token: nine randomized warmed full-seed pairs gave candidate/baseline wall 0.301729/0.268311 s and CPU 1.738646/1.577542 s. All 20 paired outputs, the separately tested emulated and generic fallback outputs and the instrumented run matched the full hash. The portable slowdown does **not** execute hardware CRC and cannot predict x86 behavior. Windows x86-v3 cross-generated assembly (with the Linux fd expression stubbed only for compilation) showed the intended chained `crc32q` instructions; actual Linux execution, official sandbox, wall time and cgroup peak remain unverified.

Portable exact-source tests cover 300,000 random CRC pairs, 100,000 query words, 9/16/17-byte boundaries, empty table, normal and forced-collision fallback, wraparound clusters and mixed valid input keys in the independently reviewed test. Independent review passed 96,874 key/case/padding/alignment cases in both normal and forced medium hash; additional tests passed displacement 32/33 and cyclic-run 64/65 acceptance boundaries. The emulated candidate passed 40 mixed-reference corpora and 40 forced-collision corpora, distributed top ten, >1 MiB lines, 250,000-document/19,000-duplicate-phrase stress and 3,072 alignment documents. The independent exact-source test is in `experiments/b-crc-medium-review/`. No Mac Docker was used.

## Required serialized Linux x86-64-v3 validation

Use the scoring-compatible SSE4.2/AVX2 Linux host and independently generated full seed-1 dataset. Both exact-source property drivers must run; `run-property.py --x86-v3` rejects a missing SSE4.2 protected-page test. The resulting process RSS is not official cgroup peak.

```sh
rustc --edition=2021 -O -C lto=fat -C codegen-units=1 -C panic=abort -C target-cpu=x86-64-v3 experiments/b-crc-medium/baseline.rs -o /tmp/b-medium-base
rustc --edition=2021 -O -C lto=fat -C codegen-units=1 -C panic=abort -C target-cpu=x86-64-v3 experiments/b-crc-medium/candidate.rs -o /tmp/b-medium-candidate
rustc --edition=2021 -O -C overflow-checks=yes -C target-cpu=x86-64-v3 --cfg b_medium_crc_forced experiments/b-crc-medium/candidate.rs -o /tmp/b-medium-forced
python3 experiments/b-crc-medium/run-property.py --x86-v3
python3 experiments/b-crc-medium-review/run.py --x86-v3
rustc --edition=2021 -O -C overflow-checks=yes -C target-cpu=x86-64-v3 experiments/b-avx2-token/classifier-property.rs -o /tmp/b-classifier && /tmp/b-classifier
python3 experiments/b-avx2-token/alignment.py /tmp/b-medium-candidate official/reference/b_index.py
B_RUST_BINARY=/tmp/b-medium-forced python3 experiments/b-bounded-fuzz.py "$PWD/experiments/b-rust-positional-adapter.py"
export B_RUST_BINARY=/tmp/b-medium-candidate
python3 experiments/b-bounded-fuzz.py "$PWD/experiments/b-rust-positional-adapter.py"
python3 experiments/b-bounded-shards.py "$PWD/experiments/b-rust-positional-adapter.py"
python3 experiments/b-bounded-boundary.py "$PWD/experiments/b-rust-positional-adapter.py"
python3 experiments/b-bounded-duplicates.py "$PWD/experiments/b-rust-positional-adapter.py"
python3 experiments/b-rust-lengthhash/compare.py --baseline /tmp/b-medium-base --candidate /tmp/b-medium-candidate --data /path/to/full-b --runs 15 --report /tmp/b-medium-x86.json
```

Run paired comparisons without concurrent load. Require repeatable x86 performance, guard/fallback tests and official practice/sandbox evidence before selection. Source-only archive contains no data, credentials or cached answers.
