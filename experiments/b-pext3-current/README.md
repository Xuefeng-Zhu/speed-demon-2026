# Track B short-key direct lookup experiment (unselected)

Baseline is byte-for-byte selected `track-b/src/main.rs`, SHA-256 `7d371fe84ce9f0fd9d3c7e6fdf02b6b37e0f1440319c654161b990cf27bb8bf3`. Candidate SHA-256 `a50ced8050898de0610dc7c5135e1b53e389a52ce95d20eb6db737bca6799a56`. No selected code, query semantics, or posting representation is changed.

BMI2 builds map the first 1–3 normalized ASCII-alphanumeric bytes injectively into 18 bits using PEXT with mask `0x5f5f5f` and index a 2^18-element `u32` ID+1 table. It requests 1 MiB only if some query term is 1–3 bytes; zero means absent. Longer tokens and non-BMI2 builds retain the baseline hashing path. Zero-padded valid bytes map to distinct six-bit values: digits 16–25, letters 33–58, padding zero. Term IDs fit this sentinel representation under the official query limits. The `b_portable_pext` flag is exclusively a test-mode arithmetic emulation, not a speed measurement.

Portable normal and forced-zero-hash property suites passed on ARM: 47,988 unique valid lowercase encodings, random 1–32-byte terms, 489,077 Plan lookups/offset cases, empty/no-short-key, misses, n=0, 1–4 boundaries and case handling. The full-seed output hash for the baseline, portable candidate and normal non-BMI2 fallback all matched `f86973c210228141bcb6f1f1b10188ad2a9b65f71e7cd7cf4590b38de4e80927`. The portable candidate and fallback each passed 40 mixed reference corpora; all three binaries passed four empty and length-boundary reference fixtures. No actual x86 BMI2 or protected-page execution, performance comparison, official result, or cgroup memory result has been obtained. The older 1–4-byte PEXT candidate used 64 MiB and was 10–11% slower on x86; this smaller table is a distinct, unproven hypothesis, and may also regress.

## Validation on Linux x86-64-v3

Run from repository root. `--x86-v3` checks every `/proc/cpuinfo` flags line for target features before compiling or executing any v3 binary, checks the exact candidate SHA and requires the actual BMI2 protected-page test. The full-data corpus and reference are not included in this experiment.

```sh
python3 experiments/b-pext3-current/run-property.py --x86-v3
rustc --edition=2021 -O -C lto=fat -C codegen-units=1 -C panic=abort -C target-cpu=x86-64-v3 experiments/b-pext3-current/baseline.rs -o /tmp/b-pext3-base
rustc --edition=2021 -O -C lto=fat -C codegen-units=1 -C panic=abort -C target-cpu=x86-64-v3 experiments/b-pext3-current/candidate.rs -o /tmp/b-pext3-cand
python3 experiments/b-pext3-current/make-forced.py /tmp/b-pext3-forced.rs
rustc --edition=2021 -O -C overflow-checks=yes -C target-cpu=x86-64-v3 /tmp/b-pext3-forced.rs -o /tmp/b-pext3-forced
python3 experiments/b-pext3-current/small-fixtures.py /tmp/b-pext3-base /tmp/b-pext3-cand /tmp/b-pext3-forced
for bin in /tmp/b-pext3-cand /tmp/b-pext3-forced; do
  B_RUST_BINARY="$bin" python3 experiments/b-bounded-fuzz.py "$PWD/experiments/b-rust-positional-adapter.py"
  B_RUST_BINARY="$bin" python3 experiments/b-bounded-shards.py "$PWD/experiments/b-rust-positional-adapter.py"
  B_RUST_BINARY="$bin" python3 experiments/b-bounded-boundary.py "$PWD/experiments/b-rust-positional-adapter.py"
  B_RUST_BINARY="$bin" python3 experiments/b-bounded-duplicates.py "$PWD/experiments/b-rust-positional-adapter.py"
done
rustc --edition=2021 -O -C overflow-checks=yes -C target-cpu=x86-64-v3 experiments/b-avx2-token/classifier-property.rs -o /tmp/b-pext3-classifier && /tmp/b-pext3-classifier
python3 experiments/b-avx2-token/alignment.py /tmp/b-pext3-cand official/reference/b_index.py
python3 experiments/b-rust-lengthhash/compare.py --baseline /tmp/b-pext3-base --candidate /tmp/b-pext3-cand --data /path/to/full-b --runs 15 --report /tmp/b-pext3-x86-a.json
```

Repeat paired full-seed testing with independent ordering and compare wall, CPU, and RSS. Validate output hashes every run and record actual feature use. Process RSS is not a parent-cgroup memory bound. Do not run overlapping benchmark workloads. No Mac Docker.

## Minimal archive paths

Include these repository-relative paths, preserving directories. They contain source and verification scripts, no data or credentials:

- `experiments/b-pext3-current/` (all files, including README, both source versions, and property tails).
- `official/reference/b_index.py`.
- `experiments/b-rust-positional-adapter.py`.
- `experiments/b-bounded-fuzz.py`, `experiments/b-bounded-shards.py`, `experiments/b-bounded-boundary.py`, and `experiments/b-bounded-duplicates.py`.
- `experiments/b-avx2-token/classifier-property.rs` and `experiments/b-avx2-token/alignment.py`.
- `experiments/b-rust-lengthhash/compare.py`.

Provide the independent full corpus separately; the archive must not include datasets or executables. The preserved pre-mask PEXT3 source is SHA-256 `8effc44c29b00e12464e370ee3dfe9ce611d601b606669efec2a06151bd5d8d0`; only the final direct-mask candidate is checked by the property runner.

Parent-run x86 dot VM paired testing found wall changes of −1.7% and +2.5% versus the exact current AVX2 baseline, with higher CPU. Across this and C PGO testing, 144 full hashes and 20 alternate-reference cases passed. The wall result is not a stable win; this remains unselected. These are native results, not official cgroup measurements.
