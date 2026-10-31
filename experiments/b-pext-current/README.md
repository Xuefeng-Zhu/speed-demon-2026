# BMI2 direct lookup rebased onto current B (unselected)

`baseline.rs` is exact current Track B SHA-256 `7d371fe84ce9f0fd9d3c7e6fdf02b6b37e0f1440319c654161b990cf27bb8bf3`. `candidate.rs` SHA-256 is `b935f0bf613107ef3d2faa7e4bc81fb52da42ec9b52790538750c17f14aa3a83`. It rebases the prior `b-pext-direct` experiment onto the current global-query implementation. It does not alter query parsing, indexing, phrase handling, Boolean evaluation or scheduling.

On BMI2 builds, 1–4 byte lowercase alphanumeric keys map injectively to four 6-bit digits using `_pext_u64`; the direct `u32` table stores term ID plus one, and zero means absent. The independent static review found no mapping or sentinel defect for the official nonempty-token grammar: digits encode 16–25, letters 33–58, padding 0; query counts keep ID+1 within u32. Longer tokens use the unchanged exact hash table. On non-BMI2 builds the original path is used. The explicit `b_portable_pext` flag is for tests only, emulating the direct map without hardware PEXT.

The direct table requests 2^24 u32 elements, exactly 64 MiB payload. This does not say how much the OS or parent cgroup charges. A missing-only or empty query input still constructs that table in BMI2/portable mode. The full program and worst-case cgroup remain unbounded by this table's size alone.

Against exact current source, native ARM portable emulation passed the official full seed-1 output SHA `f86973c210228141bcb6f1f1b10188ad2a9b65f71e7cd7cf4590b38de4e80927`, 40 mixed reference corpora, four empty/short/boundary fixtures against the reference, exhaustive 1,727,604 legal 1–4-byte encodings and uppercase equivalents, 489,077 plan/offset/missing/empty-table checks, and both ordinary and forced-zero-hash properties. The old portable implementation was slower in an earlier ARM screen; that cannot establish actual hardware BMI2 speed. Actual Linux x86 BMI2/AVX2 execution, protected-page guards, full-data target timing and cgroup memory are **not yet verified**. Do not select or submit this candidate on ARM evidence.

## Target checks

Extract at archive root, use a Linux x86-64-v3 machine with an exclusive timing window, and independently provide the full seed-1 data. `run-property.py --x86-v3` checks relevant flags on every `/proc/cpuinfo` processor before running v3 binaries, checks the exact source SHA, requires the actual BMI2 guard test, exhausts all legal direct indices, and exercises normal/forced-collision tables. The guard checks present tokens at both ends of a protected page, including lengths 1, 2, 3, 4, 5, 7, 8 and 9. The test code needs at least one accessible Linux `cpuinfo` flags line; it stops if the feature set cannot be verified.

```sh
python3 experiments/b-pext-current/run-property.py --x86-v3
rustc --edition=2021 -O -C lto=fat -C codegen-units=1 -C panic=abort -C target-cpu=x86-64-v3 experiments/b-pext-current/baseline.rs -o /tmp/b-pext-current-base
rustc --edition=2021 -O -C lto=fat -C codegen-units=1 -C panic=abort -C target-cpu=x86-64-v3 experiments/b-pext-current/candidate.rs -o /tmp/b-pext-current-cand
python3 experiments/b-pext-current/make-forced.py /tmp/b-pext-current-forced.rs
rustc --edition=2021 -O -C overflow-checks=yes -C target-cpu=x86-64-v3 /tmp/b-pext-current-forced.rs -o /tmp/b-pext-current-forced
python3 experiments/b-pext-current/small-fixtures.py /tmp/b-pext-current-base /tmp/b-pext-current-cand /tmp/b-pext-current-forced
for bin in /tmp/b-pext-current-cand /tmp/b-pext-current-forced; do
  B_RUST_BINARY="$bin" python3 experiments/b-bounded-fuzz.py "$PWD/experiments/b-rust-positional-adapter.py"
  B_RUST_BINARY="$bin" python3 experiments/b-bounded-shards.py "$PWD/experiments/b-rust-positional-adapter.py"
  B_RUST_BINARY="$bin" python3 experiments/b-bounded-boundary.py "$PWD/experiments/b-rust-positional-adapter.py"
  B_RUST_BINARY="$bin" python3 experiments/b-bounded-duplicates.py "$PWD/experiments/b-rust-positional-adapter.py"
done
rustc --edition=2021 -O -C overflow-checks=yes -C target-cpu=x86-64-v3 experiments/b-avx2-token/classifier-property.rs -o /tmp/b-classifier && /tmp/b-classifier
python3 experiments/b-avx2-token/alignment.py /tmp/b-pext-current-cand official/reference/b_index.py
python3 experiments/b-rust-lengthhash/compare.py --baseline /tmp/b-pext-current-base --candidate /tmp/b-pext-current-cand --data /path/to/full-b --runs 15 --report /tmp/b-pext-current-x86-a.json
```

Repeat the paired comparison with independent ordering and report wall, CPU, actual hardware feature coverage and process RSS. The included comparator uses a fixed randomized order by iteration; alter its seed or use an independent harness for the repeat. Parent-cgroup memory must be measured separately; this VM may lack the cgroup interface. Guard/reference tests do not prove speed. No datasets, credentials or executables are included. No Mac Docker was used.

Packaging note: the archive's explicit contents and checksum were checked, but its portable property suite was **not rerun after extraction** because a concurrent D benchmark needed the CPU window. The same exact candidate source and portable property suite passed before packaging. Run the included checks from the extracted archive; in particular, no actual x86 protected-page or BMI2 path was exercised on the Mac.

## Native x86 outcome

Parent-run shared dot VM paired full-seed testing exercised actual BMI2/AVX2: the candidate was 10.1–10.6% slower in wall time and used 9.6–10.4% more CPU. The table requests 64 MiB even for empty-query input. Actual x86 protected-page, exhaustive mapping, collision, duplicate, reference and non-BMI2 fallback checks passed; across the comparison 72 full hashes and 12 alternate references passed. These native process results are not official scoring-box or cgroup measurements. The candidate remains unselected for speed.
