# C owner-event lookahead prefetch (unselected hypothesis)

`baseline.rs` is the exact dynamic-partition source `bcd4d7715bffd8a3dc062cad6e7aa0886a96d659fcc9170735c4d4d123f67eae`. The four isolated candidates add x86-64 `_mm_prefetch` hints for a name address 1, 4 or 8 events ahead; `ahead4_cache.rs` also hints the corresponding direct-cache slot when the slice contains it. `control.rs` uses the same enumerated event loop without hints. Portable non-x86 builds execute no prefetch instruction. This experiment has not been selected, pushed, or shown to improve performance.

The hint addresses come only from checked `recs.get(offset)` and `cache.get(index)` references. Event offsets originate from parsed names within the mapped record file. The file/group fallback, exact name comparisons, collision handling and owner routing are unchanged. Even though target x86 prefetch is a nonbinding hint, pointer construction and cache slice checks still need independent review. An isolated standalone helper was compiled to x86-64 Windows assembly; its output included two `prefetcht0` instructions. That is code-generation evidence for the extracted helper only, not actual Linux x86 execution, target correctness, guard-page behavior, or speed.

On macOS ARM, where the prefetch path is compiled out, each of four variants passed 12 mixed CSV reference corpora × five worker counts, eight forced-all-zero-hash corpora × five worker counts, and a slice-edge/cache-length unit test with overflow and debug checks. Thus 400 reference comparisons and four tests passed on the no-hint path; the x86 Linux guard-page test was not executed here. No full seed-1 benchmark or independent review has run for these exact variants.

For a target check, copy `official/reference/c_join.py`, generate full public seed-1 data independently, verify AVX2 support, and serialize all work on a compatible Linux x86-64-v3 machine:

```sh
python3 experiments/c-owner-prefetch-rebase/generate.py
python3 experiments/c-owner-prefetch-rebase/verify.py --avx2
for variant in baseline control ahead1 ahead4 ahead8 ahead4_cache; do
  rustc --edition=2021 -O -C lto=fat -C codegen-units=1 -C panic=abort -C target-cpu=x86-64-v3 \
    "experiments/c-owner-prefetch-rebase/${variant}.rs" -o "/tmp/sd-c-prefetch-${variant}"
done
python3 experiments/c-owner-prefetch-rebase/compare.py --baseline /tmp/sd-c-prefetch-baseline \
  --variant /tmp/sd-c-prefetch-ahead4 --data /path/to/full-c --runs 15 --seed 101 --report /tmp/c-prefetch-a.json
python3 experiments/c-owner-prefetch-rebase/compare.py --baseline /tmp/sd-c-prefetch-baseline \
  --variant /tmp/sd-c-prefetch-ahead4 --data /path/to/full-c --runs 15 --seed 902 --report /tmp/c-prefetch-b.json
```

Run analogous pairs for each candidate and compare `control` with `baseline`, checking every hash, CPU and native RSS. The test uses Linux protected pages for both the mapped-name and final cache entry when `--avx2` runs on x86; verify the test was actually executed. Process RSS is not cgroup peak, and hidden-seed behavior and official performance remain unknown. No dataset, credential or binary belongs in this directory. No Docker was used on the Mac.
