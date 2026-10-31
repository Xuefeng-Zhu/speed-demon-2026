# Track B length-aware Rust hash comparison

`src/baseline.rs` is selected Track B at commit 073646eb00decdc0f0a4033d57941b187a5df3af (SHA-256 `805b05559c1cf73c14befbaad3f0f7cf0ef94468e64a1192709bbfe7d558ccb1`). `src/candidate.rs` (SHA-256 `60538800666ad51084600cf6d4cc008d63694b55f549fc5eb3b1582d01256fc7`) changes only dictionary hashing to process ceil(token length / 8) occupied 64-bit key words. Keys retain 32-byte zero padding and exact full-key comparisons, and the existing 64 MiB bitmap cap and bounded phrase summaries remain. Terms are nonempty 1–32 byte ASCII alphanumeric, so zero-padding is unambiguous.

On a shared ARM Mac, seven randomized full-data measured pairs (after warmup) all matched the published SHA-256; medians were 1.6454 s candidate vs 2.1095 s baseline, CPU 2.7718 vs 3.1773 s. Heavy contention makes this a screen, not an x86 or official score. `src/length-bench.json` retains the samples. A single instrumented baseline scan (`src/phases.log`) was dominated by the parallel document scan; instrumentation affects timing.

Two subsequent 11-pair dot VM x86 batches were essentially tied: candidate versus baseline 0.3955 versus 0.3943 s, then 0.3986 versus 0.4003 s. All 48 full hashes and supplied stress tests passed. CPU was slightly lower for the candidate and RSS showed no consistent benefit; these native results do not establish a wall-time win, so the baseline remains selected.

For x86-64-v3, generate the official full seed-1 data separately, then run serially without other benchmarks:

```sh
rustc --edition=2021 -O -C lto=fat -C codegen-units=1 -C panic=abort -C target-cpu=x86-64-v3 src/baseline.rs -o /tmp/b-length-base
rustc --edition=2021 -O -C lto=fat -C codegen-units=1 -C panic=abort -C target-cpu=x86-64-v3 src/candidate.rs -o /tmp/b-length-candidate
python3 compare.py --baseline /tmp/b-length-base --candidate /tmp/b-length-candidate --data /path/to/full-data --runs 7 --report /tmp/b-length-report.json
export B_RUST_BINARY=/tmp/b-length-candidate
python3 experiments/b-bounded-fuzz.py "$PWD/experiments/b-rust-positional-adapter.py"
python3 experiments/b-bounded-shards.py "$PWD/experiments/b-rust-positional-adapter.py"
python3 experiments/b-bounded-boundary.py "$PWD/experiments/b-rust-positional-adapter.py"
python3 experiments/b-bounded-duplicates.py "$PWD/experiments/b-rust-positional-adapter.py"
python3 experiments/b-packed-nonlinear-review/max_vocabulary.py "$PWD/experiments/b-rust-positional-adapter.py"
rustc --edition=2021 --test -O src/property.rs -o /tmp/b-length-property && /tmp/b-length-property
rustc --edition=2021 -C overflow-checks=yes -C opt-level=1 src/forced.rs -o /tmp/b-length-forced
B_RUST_BINARY=/tmp/b-length-forced python3 experiments/b-bounded-fuzz.py "$PWD/experiments/b-rust-positional-adapter.py"
```

The candidate passed every listed check natively: 40 reference corpora, distributed top ten and read-boundary tests, 250k-document/19k-duplicate-phrase stress, 338k distinct query terms, a 250k-present/250k-absent dictionary property test, and 40 constant-hash reference corpora with overflow checks. The comparator records wait4 per-process peak RSS, which is not official cgroup memory; target measurement and independent review remain required. No data or credentials are packaged.
