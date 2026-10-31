# B fixed short-token mask table (unselected)

The baseline is selected B source SHA-256 `7d371fe84ce9f0fd9d3c7e6fdf02b6b37e0f1440319c654161b990cf27bb8bf3`; candidate SHA-256 `64416888ab4fbc94e6aadd4668649c72d3f79336eef370fd774b5bdc2867dff5` changes only the mask used by `lookup_token` for lengths 0–8: a fixed nine-entry `u64` table replaces the existing dynamic `u128` shift and cast. The table matches the original mask for every such length, including full-width length 8. Longer token handling, exact hash/equality, tokenizer and all query paths are unchanged. This is an isolated experiment, not selected code.

After identical `rustc --edition=2021 -O -C lto=fat -C codegen-units=1 -C panic=abort` builds, one warmup and nine randomized paired runs on shared native ARM using the full public seed-1 corpus gave candidate/baseline median wall `0.235027/0.239078` s and CPU `1.518881/1.524501` s. A 15-pair repeat was `0.253150/0.254273` s wall and `1.526474/1.530395` s CPU. Every one of 52 runs, including warmups, matched the published output hash. All 90 independent mixed reference corpora including empty input and query vocabularies with no short terms also passed. Raw timing samples are `arm-a.json` and `arm-b.json`.

The wall differences (1.7% and 0.4%) and CPU differences (~0.3–0.4%) are too small and noisy to justify a target-machine recommendation. Native ARM uses the scalar classifier; Linux x86, adversarial hash flooding and parent-cgroup memory are not tested. No Docker was run on the Mac.

Reproduce with verified full data and exclusive CPU:

```sh
rustc --edition=2021 -O -C lto=fat -C codegen-units=1 -C panic=abort experiments/b-short-mask-table16/baseline.rs -o /tmp/b-mask-base
rustc --edition=2021 -O -C lto=fat -C codegen-units=1 -C panic=abort experiments/b-short-mask-table16/candidate.rs -o /tmp/b-mask-candidate
python3 experiments/b-short-lookup/independent-review.py /tmp/b-mask-candidate
python3 experiments/b-rust-lengthhash/compare.py --baseline /tmp/b-mask-base --candidate /tmp/b-mask-candidate --data /path/to/full-b --runs 15 --report /tmp/b-mask-report.json
```
