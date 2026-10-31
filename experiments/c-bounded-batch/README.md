# Track C bounded shard-batch comparison

The baseline is byte-identical to selected Track C at commit `8c273dba20ac0a98f27a1fef5614a6ef3506cc01` (SHA-256 `3e181c76981348a96b48470844ee0f8988847d32164ff935a211024861c86ad4`). Candidate SHA-256 `ca6408011023bf1894f1b3e8d53b675e5b8e4c3cb8a5c99f603ae5b60a445ac8` batches up to 32,768 name/group references per parser worker in a single fixed-capacity event vector and 1,024 fixed heads, then applies exact shared dictionary updates under one lock per nonempty shard. It uses the same permitted §2.2 CRLF boundary guarantee; no cached answers or input recognition. Source remains experimental and is not selected.

On a shared native ARM Mac, 11 measured randomized full-seed pairs after warmup all matched the published hash. Median candidate/baseline wall was 0.12850/0.14748 s, CPU 0.726/0.858 s and process peak RSS roughly 230/226 MB. This is not x86 or official cgroup performance. Earlier exploratory timings and counterfactual profiles are not official scores. Each worker's pending event vector has 32,768 entries, and fixed 1,024 heads; process memory also includes dictionary, inputs, threads and aggregation. Independent review found no correctness or concurrency defect, including 240 forced-collision/tiny-batch reference comparisons and 82,000-record/300-group stress. Target x86/cgroup measurements are required before promotion.

From archive root, generate the full seed-1 input separately using the official generator; no dataset is bundled. Use matching release flags (x86-64-v3 only on compatible CPU), serialize benchmarks, and check every hash:

```
rustc --edition=2021 -O -C lto=fat -C codegen-units=1 -C panic=abort -C target-cpu=x86-64-v3 src/baseline.rs -o /tmp/c-batch-base
rustc --edition=2021 -O -C lto=fat -C codegen-units=1 -C panic=abort -C target-cpu=x86-64-v3 src/candidate.rs -o /tmp/c-batch-candidate
python3 experiments/c-rust-independent.py --source src/candidate.rs --seeds 24
python3 experiments/c-nameowned/multigroup.py src/candidate.rs official/reference/c_join.py
python3 tests/batch-review.py src/candidate.rs
python3 experiments/c-crlf-boundary/compare.py --baseline /tmp/c-batch-base --variant /tmp/c-batch-candidate --data /path/to/generated-full-c --runs 11 --report /tmp/c-batch-x86.json
```

The multigroup test forces constant hashes and covers 240 groups across six worker counts. The 70,037-record, 130-group batch-boundary test forces normal/constant hashes with 1/2/3/7 workers; it covers events across multiple flushes and compares reference bytes. All tests passed locally. The comparator records wall, CPU and wait4 process RSS; Linux process RSS is KiB and is not official warmed-cgroup memory. Check exact source checksums, seed, compiler and individual runs. No Mac Docker was used.

The repository also retains `counterfactual-report.json`: those non-output-equivalent builds deliberately set `names_distinct` to zero while timing parsing, one hash, or hash plus lock without dictionary work. Other columns were checked against baseline. They are profiling aids only, not valid candidate implementations or official scores; median native ARM wall/CPU seconds were baseline 0.2615/0.8762, parse-only 0.0707/0.3068, hash-only 0.0816/0.3451, and hash-plus-lock-only 0.1052/0.5211. Different behavior alters caching and contention, so differences are not an additive decomposition.
