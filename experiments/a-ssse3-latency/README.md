# Track A SSSE3 decimal decoder (experimental, not selected)

This candidate replaces the 1–7-digit latency decoder's scalar SWAR combination with x86 SSSE3 `PMADDUBSW` and `PMADDWD` when compiling for an SSSE3 target. Non-SSSE3 builds retain the exact baseline; latencies of at least eight digits use the unchanged scalar loop. The decoder reads the same guarded 8-byte word as the baseline and does not add loads. The input is decimal, unsigned and at most u32 per the official spec.

Exact selected no-prefault baseline SHA-256 `16ae5a2e4df27269dbcc2f7b21bb9ad1022081d84e68e5b2c3f5b122a7cb04e2`; candidate `a168200fb13f60df2407a2aae13085768d7af52927e077d202d16ea4e975d1d2`. Independent static review found that the decimal pairs and quads fit the signed SIMD intermediates without saturation, and the final scalar combination fits u32. An overflow-checked portable semantic model passed all 10,000,000 values of 0–9,999,999. An exact-source fallback build on ARM passed 11,000,216 numeric and protected-page checks and the full seed-1 hash. The actual SIMD path has **not** executed; these checks do not establish its correctness or speed on x86.

Cross-generated x86-64-v3 Windows-target assembly for the isolated helper contains `vpmaddubsw`, `vpmaddwd`, moves and a 32-bit `imul` instead of the baseline's two 64-bit `imul` operations and masks. This is a hypothesis, not a timing or Linux binary claim; SIMD transfer latency and surrounding instructions may make it slower. No Docker was run on the Mac.

## Target testing

On a disposable SSSE3-capable Linux x86-64 host, with separately generated full seed-1 data and no competing benchmarks:

```
python3 property.py
rustc --edition=2021 -O -C overflow-checks=yes vector-model.rs -o /tmp/a-simd-model
/tmp/a-simd-model
python3 compare.py --data /path/to/full-a --report /tmp/a-simd-pairs.json --runs 15 --threads 12
rustc --edition=2021 -O -C lto=fat -C codegen-units=1 -C target-cpu=x86-64-v3 candidate.rs -o /tmp/a-simd
python3 tests/test.py --binary /tmp/a-simd --io directories
python3 tests/page_end_test.py --binary /tmp/a-simd --reference official/reference/a_ingest.py
python3 tests/latency_grid_test.py --binary /tmp/a-simd
```

`property.py` compiles the actual candidate helper with `+ssse3` on x86, exercises all 0–9,999,999 latencies, 1,000,000 random u32 values, powers/maximum values, offsets, and a PROT_NONE guard page. It uses overflow checks off to match release, because the original scalar SWAR intentionally wraps intermediate arithmetic. The standalone semantic model is overflow-checked. The comparator randomizes paired order and verifies the published output hash after every full run; it reports native process RSS, not official parent-cgroup peak. A target must support SSSE3 (the official i5 supports AVX2); no claim follows from ARM fallback or Windows cross-compilation alone. Examine correct outputs, variability, cgroup memory and the official practice board before selection.
