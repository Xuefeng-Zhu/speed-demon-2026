# B direct-index bitmap cache (not selected)

The candidate replaces the per-worker `HashMap<term, Vec<u64>>` dense bitmap cache with a `Vec<Option<Vec<u64>>>` indexed by term ID. Bitmap payload remains capped at the same per-worker budget; the vector itself consumes additional memory proportional to the query vocabulary. Query algebra, phrase summaries and exact token lookup are unchanged. This is an isolated experiment.

Seven measured randomized native shared-Mac ARM pairs after one warmup each matched the published full seed-1 hash. Candidate vs baseline median wall was 0.261543 vs 0.257771 s, and median CPU 1.555762 vs 1.576870 s. Maximum per-process RSS across measured samples was 554,041,344 vs 534,036,480 bytes. The modest wall regression, small CPU gain, and extra memory do not justify promotion on this noisy ARM scalar-path screen; process RSS is not cgroup peak, and x86 behavior is unknown. All 40 mixed-reference fuzz corpora and the distributed shard/top-ten/overlap fixture passed. The raw data is `report.json`.

Compile both Rust files with identical release/target flags and use `python3 experiments/b-rust-lengthhash/compare.py --baseline /path/to/base --candidate /path/to/candidate --data /path/to/full-b --runs 7 --report /tmp/b-direct-cache.json`. Generate input separately. No Mac Docker was used.
