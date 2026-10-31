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

To reproduce those historical binaries, copy Cargo.toml, Cargo.lock and src/ from `experiments/track-d-dense/` into a temporary directory. Run `cargo build --release --offline --manifest-path <temp>/Cargo.toml`; preserve the resulting executable as the six-worker version. Change `0..6.min(queries.len())` to `0..12.min(queries.len())` in the temporary `src/main.rs`, rebuild, and preserve the result as the twelve-worker version. Run each with `DATA_DIR=<full-data-dir> OUT_DIR=<existing-output-dir> <binary>`, alternating order and verifying the output SHA-256 after each run. Avoid concurrent jobs and repeat on the scoring machine before drawing conclusions.

A separate three-pair experiment compared six and three workers under more variable contention: six was 1.308, 1.864, 2.515 seconds and approximately 459–514 MB RSS; three was 1.917, 1.619, 3.140 seconds and approximately 381–388 MB RSS. The noisy measurements do not establish the better target-machine K. Three workers is another candidate for a serial controlled experiment; it was not selected based on these numbers.

## Controlled local comparison

Five interleaved full-data pairs after warmup on macOS ARM: 12 versus 6 workers median 1.018773 versus 1.102140 s; 6 versus 3 workers median 1.110951 versus 1.422599 s. Every output matched the full hash. Earlier separate Mac RSS checks show approximately 766 MB (12) versus 515 MB (6). Six remains provisional pending board measurement. Details: `experiments/bench-d-12-vs-6.json` and `experiments/bench-d-6-vs-3.json`. These are local measurements, not board scores.


## Native x86 dot VM follow-up

The six-worker candidate passed three small differential seeds and the published full-data hash after compilation with rustc 1.99.1. Five-run native medians were 2.321 s and 357.2 MiB peak RSS for six workers, versus 2.195 s and 597.2 MiB for a reconstructed twelve-worker variant. Applying the time and memory exponents to these local figures favors six workers by about 7.8% on K, assuming the other factors are equal. This is not an official board result; its time and cgroup memory aggregation differ from these local metrics. Full context and calculation are in `experiments/dot-vm.md`.


## Native x86 seen16 follow-up

The seen16 variant was provisionally selected after a shared dot VM reported 2.144 s versus 2.318 s for its prior dense baseline and about 11% lower process RSS; the supplied full, alternate, randomized-oracle, epoch and extreme checks passed. The time/memory factors alone imply approximately 1.064× K, before source-size and dependency effects. The sparse alternative was 1.991 versus 2.276 s with slightly lower RSS, but the exact RSS and official scc counts were not supplied. Both estimates are close; seen16 is the smaller change and sparse remains available for board testing. See `experiments/dot-vm.md`. The selected version passed the offline restricted ARM Docker full-data hash in 1.90 s including startup and fresh tiny seeds 2, 17 and 4242. The first subsequent board run is recorded below.


## First official live-board practice run

The public seed-1 practice run at commit `f45c4cf3f707123e705b930c6b1f08b8facefdc5` is `run-c58a137eb965`. It passed the check, build, correctness, timeout and sandbox gates. The board reports T=1.808861 s, M=334454784 bytes, S=169, D=1, K=6.283108 and 39.908727 machine points. This is a single live-board run, not the final five-run hidden-seed score. Source and snapshot: `experiments/board-f45.json`.


## Live-board practice run at 664ba1a

Run `run-6459b46e9e69` at commit `664ba1aafb0d765427f49d5ad933b6c1a18b0f24` passed check, build, correctness, timeout and sandbox. The board reports T=1.716724 s, M=334192640 bytes, S=169, D=1, K=6.450524 and 40.47975 machine points. This single public-seed practice run is not final hidden-seed scoring. See `experiments/board-664.json`.


## Live-board practice run at 2fc9110

Run `run-744fbf4164a5` at commit `2fc9110d0c2acfc880350efbc240f5aa4620bd99` passed check, build, correctness, timeout and sandbox. The board reports T=1.72154 s, M=333930496 bytes, S=169, D=1, K=6.442506 and 40.452742 machine points. This is a single public-seed practice run, not final hidden-seed scoring. See `experiments/board-2fc.json`.
