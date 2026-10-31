# B packed 7-byte signature table (isolated, unselected)

Baseline `baseline.rs` is exact selected Track B source SHA-256 `7d371fe84ce9f0fd9d3c7e6fdf02b6b37e0f1440319c654161b990cf27bb8bf3`. The candidate changes only the short-token lookup table on x86-64 builds with compile-time BMI2, or in explicit portable test emulation. `_pext_u64` encodes the first seven case-folded alphanumeric bytes in 42 bits, plus an eighth-byte-present flag; a 21-bit global term ID occupies the remainder of the u64 slot. For tokens of eight bytes, an equal signature additionally checks the original complete key. The table is at most half full. With more than 2^21 interned terms, or on non-BMI2 targets, the unchanged original table is used. Phrase summaries and bitmap limits are unchanged.

Zero padding is distinguishable because legal tokens are nonempty ASCII alphanumeric: each normalized byte maps injectively to 16–25 (digits) or 33–58 (letters), and zero maps to zero. The eighth-byte check preserves exactness for signatures shared by up to 36 8-byte alphanumeric keys. Every equality involving the eighth byte reads the existing exact key. A read-only independent review found no concrete defect under the published token grammar. It does not establish performance or a universal cgroup bound. The packed table uses 8 bytes per short slot versus 4 in the original, before allocator overhead.

Portable emulation passed exhaustive 47,988 length 1–3 tokens and uppercase forms, all 36 eighth-byte suffixes sharing a prefix plus a missing suffix, empty token lookup, forced constant-hash collision, and exact ID limits at 2^21 and 2^21+1. Instrumenting a full public seed-1 run reported 75,747 total terms, packed mode active, and 131,072 slots; its hash matched `f86973c210228141bcb6f1f1b10188ad2a9b65f71e7cd7cf4590b38de4e80927`. Portable checked builds passed 40 mixed official-reference corpora, 90 independent reference corpora, >1 MiB lines, distributed top ten/overlap, and 250,000-document/19,000 duplicate-phrase stress. A normal non-BMI2 fallback also matched the full public hash. These are correctness results, not benchmarks. Actual x86 BMI2 execution, guard pages, forced-collision end-to-end differential cases, target wall time, Linux sandbox and cgroup peak remain untested. No Mac Docker was used.

## Independent x86 test (serialized)

Generate the official full seed-1 dataset independently. Do not benchmark concurrently. Use Rust 1.99.1 and actual x86-64-v3; do not use `pext_emulate` for performance measurements. This archive has no dataset, credentials, executable or cached answer files. Run from its root:

```sh
python3 experiments/b-packed-pext22/run-property.py --x86-v3
rustc --edition=2021 -O -C lto=fat -C codegen-units=1 -C panic=abort -C target-cpu=x86-64-v3 experiments/b-packed-pext22/baseline.rs -o /tmp/b-pext22-base
rustc --edition=2021 -O -C lto=fat -C codegen-units=1 -C panic=abort -C target-cpu=x86-64-v3 experiments/b-packed-pext22/candidate.rs -o /tmp/b-pext22-candidate
python3 experiments/b-short-lookup/independent-review.py /tmp/b-pext22-candidate
export B_RUST_BINARY=/tmp/b-pext22-candidate
python3 experiments/b-bounded-fuzz.py "$PWD/experiments/b-rust-positional-adapter.py"
python3 experiments/b-bounded-boundary.py "$PWD/experiments/b-rust-positional-adapter.py"
python3 experiments/b-bounded-shards.py "$PWD/experiments/b-rust-positional-adapter.py"
python3 experiments/b-bounded-duplicates.py "$PWD/experiments/b-rust-positional-adapter.py"
python3 experiments/b-rust-lengthhash/compare.py --baseline /tmp/b-pext22-base --candidate /tmp/b-pext22-candidate --data /path/to/full-b --runs 15 --report /tmp/b-pext22-first.json
python3 experiments/b-rust-lengthhash/compare.py --baseline /tmp/b-pext22-base --candidate /tmp/b-pext22-candidate --data /path/to/full-b --runs 15 --report /tmp/b-pext22-repeat.json
```

`--x86-v3` refuses a non-x86/absent BMI2 host and executes both normal and forced-hash property suites, including a Linux guard-page test. Additionally verify actual `pext` instruction execution and packed-mode activation on the full seed by temporarily inserting an stderr diagnostic after `plan.build_short()`; the diagnostic build must not be used for timing. Run x86 AVX2 classifier guards from the separately reviewed repository suite and compare PGO-trained variants if native measurements warrant further work. Process RSS reported by the comparator is not official parent-cgroup peak. If this experiment is slower or tied, keep the current B build.
