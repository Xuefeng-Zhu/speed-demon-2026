# Performance log

| Step | Change | Board run ID | Time | Memory |
|---|---|---|---|---|
| 0 | Official reference | calibration | 72.69 s | 893 MB |
| 1 | CSR, bidirectional Dijkstra, 12 workers | not run | not measured on board | not measured on board |
| 2 | Six workers to reduce per-thread graph-sized state | not run | not measured on board | not measured on board |

Local Mac check: official sample seed 1 took 0.37 s wall, under concurrent workload; this is a single local observation, not comparable to the official reference or a board result. Its output SHA-256 `a4c76ed030bc7e365db33191f6cf74708fba7f25eb48d64c8c4279f2e57046a0` matches the official sample digest. Sample seed 7 matches the official reference byte-for-byte, both SHA-256 `88bf36c94620505d1beafe7cd56a08dc2d261b71f9824d2f764d5ce6e5d7872e`. Board measurement is pending; no run ID has been invented.

The official seed-1 full graph and query input hashes matched the published values; its output matched the published SHA-256 `a23dbdf0a3e49cc8901310a9ee1dc6a9a569a85297b6da75c2a7002cb2ed277e`. One local Mac run took 1.07 s wall, 4.49 s user, under concurrent workload; `/usr/bin/time -l` could not read `kern.clockrate` due to sandbox permissions, so peak RSS was not captured. An independent Python Dijkstra oracle also matched 4,500 queries on 30 randomly generated directed graphs with zeros and maximum 32-bit edge weights. These checks do not replace the Linux sandbox, board, or unseen official holdout.

## Local worker-count experiment

Six-worker candidate versus twelve-worker baseline on seed-1 full, alternate order, using release builds on the local Mac, while other tasks were running. Six paired timings, seconds:

- 12 workers: 1.341, 1.353, 1.223, 1.150, 1.237, 1.194 (median 1.230).
- 6 workers: 2.042, 1.445, 1.340, 1.260, 1.319, 1.248 (median 1.330).

A second three-pair run using Python `resource.getrusage(RUSAGE_CHILDREN).ru_maxrss` in a fresh process for each measurement reported 12 workers: 1.124/765,853,696, 1.022/765,968,384, 1.074/766,181,376 (seconds/bytes); 6 workers: 1.149/514,768,896, 1.080/514,703,360, 1.071/514,572,288. Mac RSS is not the Linux cgroup memory measure; scheduling and CPU contention confound wall times. Reduced memory makes six workers promising for the score, but this must be remeasured serially on the target machine.

The six-worker version matched the official full-seed-1 hash, the official reference on sample seed 7, and sample seed 2 (`70e94813fc6fbee12c22cc040bc4a4629c70508d13eaab2bfabbdd75e1d51aed`).

To reproduce each binary from this six-worker candidate, copy Cargo.toml, Cargo.lock and src/ into a temporary directory. Run `cargo build --release --offline --manifest-path <temp>/Cargo.toml`; preserve the resulting executable as the six-worker version. Change `0..6.min(queries.len())` to `0..12.min(queries.len())` in the temporary `src/main.rs`, rebuild, and preserve the result as the twelve-worker version. Run each with `DATA_DIR=<full-data-dir> OUT_DIR=<existing-output-dir> <binary>`, alternating order and verifying the output SHA-256 after each run. Avoid concurrent jobs and repeat on the scoring machine before drawing conclusions.

A separate three-pair experiment compared six and three workers under more variable contention: six was 1.308, 1.864, 2.515 seconds and approximately 459–514 MB RSS; three was 1.917, 1.619, 3.140 seconds and approximately 381–388 MB RSS. The noisy measurements do not establish the better target-machine K. Three workers is another candidate for a serial controlled experiment; it was not selected based on these numbers.

## Controlled local comparison

Five interleaved full-data pairs after warmup on macOS ARM: 12 versus 6 workers median 1.018773 versus 1.102140 s; 6 versus 3 workers median 1.110951 versus 1.422599 s. Every output matched the full hash. Earlier separate Mac RSS checks show approximately 766 MB (12) versus 515 MB (6). Six remains provisional pending board measurement. Details: `../../experiments/bench-d-12-vs-6.json` and `../../experiments/bench-d-6-vs-3.json`. These are local measurements, not board scores.
