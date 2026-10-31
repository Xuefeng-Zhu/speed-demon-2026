# Guarded one-pass D loader (unselected)

`baseline.rs` is exact selected hybrid SHA-256 `671c639be3400209e83e080dfb54947affd30ca71dc34ec17804d24d70292d9c`. `candidate.rs` SHA-256 `77f764359aa3189f73e37d2b411ba80a700ee66ee25a40c0286e658ab45f52d4` retains the same CSR builder and query search. This is isolated and not selected or submitted.

The candidate first attempts the existing one-pass block-bucketing loader. Each parser reserves variable-sized input, edge-bucket, and outer bucket-vector metadata requests against one cumulative 320 MiB atomic ledger. Edge buckets have a fixed logical capacity equal to the old initial requested capacity; it checks both forward and reverse slots before either push, so successful fast buckets never grow or reallocate. If any reservation, logical cap or allocation check fails, workers receive an advisory cancellation flag; every worker is joined and **all partial outputs are dropped**, then the exact two-pass-count loader reopens the input and starts again. No partial CSR or output is accepted. The exact retry's requested edge capacity is separately bounded by 2*m; its allocations and the CSR/search state are not included in the fast-path 320 MiB ledger.

The ledger charges requested `Vec` capacity before allocation and any reported excess only **after** allocation. The fast path has no bucket-reallocation transient, but allocator over-allocation may be physically acquired before excess is detected. The ledger excludes fixed thread handles and control metadata, exact-retry/CSR/search allocations, allocator retention, thread stacks, kernel and page-cache charges. Kernel overcommit/OOM while pages are touched cannot be caught by this mechanism. The exact retry itself may fail on allocation just as the baseline would. Therefore **320 MiB is not a strict allocation, process-RSS or parent-cgroup bound**, and this experiment does not prove the 8 GiB cap for all valid inputs.

For official m=5,000,000 and t=12, old initial fast edge-bucket requests total about 135.2 MB; exact retry requests 120 MB of edge tuples. A conservative conditional accounting that adds both sets, both input-buffer passes and an extra thread-stack allowance gives approximately 1.93 GB for listed search, loader, input/cache and stacks, before unspecified allocation/kernel/harness charges; see `memory.md` and the independent review at `../track-d-guarded-independent/README.md`. This accounting assumes the official full grammar/dimensions, target `Edge` tuple size and stack estimates. It is not a cgroup peak proof.

`verify.py` built the exact frozen candidate under debug and overflow checks, forcing budgets 0/1 and logical per-bucket caps 0/1. A skew fixture confirmed actual fallback for each forced failure, fast path on normal input, and exact output. The default candidate passed 16,000 random graph queries against an independent Dijkstra oracle. `../track-d-guarded-independent/` independently instrumented 480 loader configurations per variant, five variants (2,400 total), comparing both CSR edge multisets and asserting no bucket growth, global logical budget, and zero active parser workers before retry. That test observes worker exits but Rust return/ownership semantics—not allocator lifetime instrumentation—establish dropping `parsed` before retry. A second independent 2,400-case pass observed both budget/cap rejection and cancellation. `fault.py` injected a test-only failure into 12 initial allocation positions across 1/2/7/12 workers; every case observed the injected failure and complete exact fallback with correct answers. An instrumented full public seed-1 run selected `GUARD_FAST` and matched SHA-256 `a23dbdf0a3e49cc8901310a9ee1dc6a9a569a85297b6da75c2a7002cb2ed277e`.

One serialized 15-pair native ARM full-seed batch reported median wall `0.254075` candidate versus `0.251899` s baseline (+0.86%), median CPU `1.82839` versus `1.81832` s and maximum process RSS approximately 613.4 MB for both. All 32 runs including warmups matched the full hash; raw observations are `arm-a.json`. This small difference can be noise and is not a Linux x86, official or cgroup result. A clean timing repeat, actual x86 full/alternate/skew tests and official parent-cgroup results are still necessary. No Docker ran on the Mac.

To reproduce the finite tests and native comparison with independent full seed-1 data:

```sh
python3 experiments/track-d-guarded-loader/verify.py
python3 experiments/track-d-guarded-loader/fault.py
python3 experiments/track-d-guarded-loader/skew.py --edges 10000 --threads 12
python3 experiments/track-d-guarded-independent/run.py
python3 experiments/track-d-guarded-loader/compare.py --data /path/to/full-d \
  --build-dir /tmp/d-guarded-build --runs 15 --seed 4371 --report /tmp/d-guarded-result.json
```

A 10,000-edge/12-worker `skew.py` smoke observed the default-cap fallback and exact answers. `skew.py` generates only temporary data, forces a test-only worker count, and asserts actual default-budget bucket-cap fallback and exact answers on a high-skew graph. It supports `--edges 5000000 --nodes 1740512 --threads 12` for a larger VM stress; this is synthetic and not a scoring/cgroup proof. A whole-process timeout is enforced, and cleanup uses `TemporaryDirectory`; external SIGKILL may leave files behind.

## Native x86 outcome

Parent-run shared dot VM paired full-seed batches measured the candidate 0.8% slower and then 2.5% faster in wall time, while CPU was 1.4–1.5% higher. Across the comparison 72 full hashes, eight alternate references, 2,400 CSR checks and 24 failure/rollback checks passed. A synthetic 5,000,000-edge all-wide skew stress reported process peak RSS of 336,820 KiB for the guarded candidate versus 207,128 KiB for the baseline, about 63% higher. These native process measurements are not official scoring-box parent-cgroup peaks or a worst-case 8 GiB proof. There is no stable speed gain, so the candidate remains unselected.
