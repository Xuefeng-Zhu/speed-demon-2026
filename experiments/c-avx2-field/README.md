# C AVX2 field delimiter search — unselected

`baseline.rs` is the exact selected SWAR parser, SHA-256 `f71a22c0642250010d967cfb493fbfb95bab01f1c3e4dedac0b93fb2987e80ef`. `candidate.rs` (`41811d86e01bb7773b7fa314e1384b2879e39dcd53aee0b2ea7406f2f4a8060d`) searches 32 bytes at a time using AVX2 equality and movemask; `hybrid.rs` (`81bf5154261f56153e2ef347072b9f789eb4dd272b111f0cebd0034649dc37b9`) first checks eight bytes with the existing SWAR method. Both use guarded in-slice unaligned loads, return the first delimiter, and retain the existing SWAR tail and unchanged CSV escape logic. The vector path is compiled only when the x86-64 build target explicitly enables AVX2; other targets use the selected parser. The official `x86-64-v3` build enables it. No cached answers or input recognition are used. The candidates remain unselected.

An independent static reviewer found no load-bound or first-delimiter defect: movemask order matches byte order and the first-8 hybrid advances only after proving the word has no match. Both extracted helpers cross-compiled to x86-64-v3 Windows-target assembly containing guarded `vpcmpeqb` and `vpmovmskb`. **No x86 or Linux AVX2 path has been executed or timed**; Windows cross-generated assembly is not evidence of Linux execution. On Mac ARM, where the vector path is compiled out, both variants passed 15,145,280 delimiter property comparisons, 76,924 protected-page checks, 24 mixed corpora at five worker counts, 357 CRLF/quoted-newline boundary cases, and the full public output hash. No Mac Docker was used. Native ARM timings are not evidence of vector speed.

On a compatible x86-64-v3 Linux host, first verify the CPU supports the required instruction set. Generate the official full seed-1 dataset separately and run the following **serialized**, without competing benchmarks:

```sh
rustc --edition=2021 -O -C lto=fat -C codegen-units=1 -C panic=abort -C target-cpu=x86-64-v3 experiments/c-avx2-field/baseline.rs -o /tmp/c-avx-base
rustc --edition=2021 -O -C lto=fat -C codegen-units=1 -C panic=abort -C target-cpu=x86-64-v3 experiments/c-avx2-field/candidate.rs -o /tmp/c-avx-direct
rustc --edition=2021 -O -C lto=fat -C codegen-units=1 -C panic=abort -C target-cpu=x86-64-v3 experiments/c-avx2-field/hybrid.rs -o /tmp/c-avx-hybrid
python3 experiments/c-avx2-field/check-asm.py --source experiments/c-avx2-field/candidate.rs
python3 experiments/c-avx2-field/check-asm.py --source experiments/c-avx2-field/hybrid.rs
python3 experiments/c-avx2-field/property.py --avx2
python3 experiments/c-avx2-field/guard.py --avx2
python3 experiments/c-avx2-field/property.py --avx2 --hybrid
python3 experiments/c-avx2-field/guard.py --avx2 --hybrid
python3 experiments/c-avx2-field/independent.py --avx2 --source experiments/c-avx2-field/candidate.rs --seeds 24
python3 experiments/c-avx2-field/independent.py --avx2 --source experiments/c-avx2-field/hybrid.rs --seeds 24
python3 experiments/c-avx2-field/cut_oracle.py --avx2
python3 experiments/c-avx2-field/cut_oracle.py --avx2 --hybrid
python3 experiments/c-nameowned/compare.py --baseline /tmp/c-avx-base --variant /tmp/c-avx-direct --data /path/to/generated-full-c --runs 15 --report /tmp/c-avx-direct.json
python3 experiments/c-nameowned/compare.py --baseline /tmp/c-avx-base --variant /tmp/c-avx-hybrid --data /path/to/generated-full-c --runs 15 --report /tmp/c-avx-hybrid.json
```

Property/guard commands explicitly require AVX2 and compile with `+avx2`; the reference/boundary commands build x86-64-v3. Repeat the paired timing batches. The comparator checks each output against the public hash and records wall, CPU and process RSS; official warmed-cgroup memory and board scoring are separate. The `--avx2` flag is essential: without it these tests exercise the portable fallback.
