# B four-block token classification (unselected)

This isolated candidate classifies four independent 32-byte blocks before consuming their masks in document order. It carries the original open-token state through each block and into the original tail loop, so tokens and phrases can cross any block boundary. All four classifier loads require at least 128 bytes before the current document's LF. The fixed four-mask array is stack allocated; there is no additional per-document heap allocation. Query parsing, dictionary equality, phrase/BOOL handling, global bitmap cap and outputs are unchanged.

Exact selected `baseline.rs` SHA-256: `7d371fe84ce9f0fd9d3c7e6fdf02b6b37e0f1440319c654161b990cf27bb8bf3`. Isolated `candidate.rs`: `7ffd820e9cfebdd93c515edc9a721c54328f04a7b470490d953df1bf93fd0142`. It remains unselected and has not been tested on the official board.

Independent static review found no concrete ordering, cursor, shift or guarded-load defect. `../b-classify-four-independent/` appends tests to an exact-source checked build. Native macOS ARM passed 493,216 exhaustive-mask and random documents, 1,520 boundary/phrase-order cases, and 48 whole-document scans against left and right inaccessible guard pages, including 127/128/129 and 255/256/257-byte texts, crossing tokens, >32-byte tokens and non-ASCII separators. A further 40 mixed official-reference corpora passed. The normal source's AVX2 path and actual Linux guard pages have not been executed locally.

On a shared native ARM host, randomized full public seed-1 comparisons after warmups produced candidate/baseline medians: nine pairs wall `0.226159/0.233162` s, CPU `1.460044/1.524125` s; fifteen-pair repeat wall `0.227816/0.235392` s, CPU `1.464359/1.522770` s. All 52 full outputs including warmups matched the published hash. Median native process RSS was ~521.5/521.7 MB and ~520.4/521.9 MB respectively; maxima varied, reaching ~538.6 MB candidate on repeat. Raw observations are `arm-screen.json` and `arm-repeat.json`. The ARM scalar path and shared-host timings are not x86, official wall or parent-cgroup evidence. No Mac Docker was used.

## Linux x86-64-v3 validation

Extract at the archive root on Linux x86-64; independently supply the full public seed-1 dataset. The first command checks required CPU flags including BMI1/BMI2 and LZCNT/ABM **before** compiling/running x86-64-v3 code, hashes the exact candidate, exercises actual AVX2, and runs the exact new document loop against protected pages. If preflight fails, stop; do not force an illegal instruction.

```sh
python3 experiments/b-classify-four-independent/run.py --x86-v3
rustc --edition=2021 -O -C overflow-checks=yes -C target-cpu=x86-64-v3 experiments/b-avx2-token/classifier-property.rs -o /tmp/b-four-classifier
/tmp/b-four-classifier
rustc --edition=2021 -O -C lto=fat -C codegen-units=1 -C panic=abort -C target-cpu=x86-64-v3 experiments/b-classify-four-current/baseline.rs -o /tmp/b-four-base
rustc --edition=2021 -O -C lto=fat -C codegen-units=1 -C panic=abort -C target-cpu=x86-64-v3 experiments/b-classify-four-current/candidate.rs -o /tmp/b-four-candidate
python3 experiments/b-avx2-token/alignment.py /tmp/b-four-candidate official/reference/b_index.py
export B_RUST_BINARY=/tmp/b-four-candidate
python3 experiments/b-bounded-fuzz.py "$PWD/experiments/b-rust-positional-adapter.py"
python3 experiments/b-bounded-shards.py "$PWD/experiments/b-rust-positional-adapter.py"
python3 experiments/b-bounded-boundary.py "$PWD/experiments/b-rust-positional-adapter.py"
python3 experiments/b-bounded-duplicates.py "$PWD/experiments/b-rust-positional-adapter.py"
python3 experiments/b-classify-four-current/compare.py --baseline /tmp/b-four-base --candidate /tmp/b-four-candidate --data /path/to/full-b --runs 15 --seed 1031 --report /tmp/b-four-x86-a.json
python3 experiments/b-classify-four-current/compare.py --baseline /tmp/b-four-base --candidate /tmp/b-four-candidate --data /path/to/full-b --runs 15 --seed 2032 --report /tmp/b-four-x86-b.json
```

The paired comparator runs serially, randomizes each order, checks the complete published hash for every run, and records process wall/CPU/RSS; native RSS is not cgroup peak. Compare target results and actual parent-cgroup memory separately; never infer an official or hidden-data score from these tests. The package includes source, reference and scripts only; no credentials, data, executables or answer caches.

## Native x86 outcome

Parent-run shared dot VM paired full-seed batches exercised the actual AVX2 path: the candidate was 1.3–2.3% slower in wall time and used 1.3–4.7% more CPU, with native process RSS unchanged. All 72 full hashes, eight alternate references and the 128-byte loop, protected-page, phrase/token ordering and stress checks passed. These are native VM results, not official scoring-box or cgroup measurements. The ARM gain did not reproduce and the candidate remains unselected.
