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

## Rust radix-heap candidate

The current candidate selectively adopts the Track D design from PR commit `f348fd7227d4afabe6feaf2b7389f7ef73863178`; the PR itself was not merged. On a shared x86 dot VM, five alternating full-data pairs had native medians 1.1298 s for this candidate versus 2.2681 s for the preceding selected version, with all full hashes matching. Those times are not official cgroup scores; matched memory and pinned source counts were not supplied. The previous source is preserved in `experiments/track-d-seen16/`.

An offline release build matched the full seed-1 hash. Independent oracle tests covered 80 random graphs at each of five worker configurations, and another 150 random directed graphs with default and forced 12 workers; cases included zero and maximum u32 weights, self-loops, parallel edges and disconnected nodes. A maximum-size chain with maximum weights and repeated-query tests also passed. Native Mac checks and the dot VM are not hidden-data or official Linux container verification. The official practice run at 02d7b4c for the preceding version was `run-5caa97af7b2c`: T=1.753772 s, M=334098432 bytes, S=169, K=6.382387; all gates passed. See `experiments/board-02d.json`.

The unchanged Linux candidate subsequently matched the full seed-1 SHA-256 in a restricted offline ARM Linux container. The integrated A–D tree also matched the official references for tiny seeds 2 and 17 on ARM Linux.

Official public-seed practice run `run-5458bb4b4329` at commit `89795bbc852b5e24e9f976c7291b3c3a21101361` passed all gates: T=0.872892 s, M=453,419,008 bytes, S=233, K=8.110433. The prior implementation at 02d7b4c had K=6.382387. These are separate practice measurements, not final holdout results. See `experiments/board-897.json`.

## Meeting checks on distance improvement

The speed-focused candidate checks the opposite tentative distance only when a relaxation improves its side. When a node has distances on both sides, the later successful improvement has checked their sum; a non-improving relaxation cannot improve that pair. Independent review found no defect and verified all 4,096 three-node directed graphs over absent/zero/one/u32-max edges against Floyd–Warshall, plus mixed-weight and repeated-query chain checks. The dot VM reported 1.0545 s versus 1.1347 s for the previous source, median process RSS 352.9 versus 351.9 MiB, and one retained candidate outlier at 383.4 MiB. Full hashes, 112,000 independent oracle queries across worker counts, extreme tests and alternate references passed. These are native VM observations, not official scoring-box results. The prior source is `experiments/d-meeting-baseline-15c/main.rs`; experiment and ARM measurements are in `experiments/track-d-meeting-update/`. At 15c6be0, previous run `run-1ce368e52c49` passed all gates with T=0.802058 s, M=455,892,992 bytes, S=233, K=8.451791 (`experiments/board-15c.json`).

Official practice `run-124e37e0677e` at b9c2b54 passed every gate: T=0.717778 s, M=455,106,560 bytes, S=236, K=8.920170. The previous run measured T=0.802058 s and K=8.451791. See `experiments/board-b9.json`; these are separate public-seed runs.

## Proposed PR line reduction with meeting update

The isolated merge candidate combines PR 385a930's structural rewrite with the selected meeting-update optimization, touched-node deduplication and self-query handling. Full seed-1, independent random and exhaustive directed-graph oracles, maximum-weight chain and repeated-query tests passed. On the shared x86 dot VM it measured 1.196 s versus 1.1255 s for the existing meeting-update source. The speed-first merge retains the existing implementation; the tested rewrite is `experiments/pr1-c634/trimmed-d-meeting.rs`. These are native VM observations, not official scores.

## Balanced bidirectional frontiers

The current candidate chooses the smaller priority queue, breaking ties by smaller minimum distance, while retaining per-side minimum order and the existing stopping bound. Two independent reviews found no correctness defect; successful relaxation checks and initial endpoints preserve the stopping proof. The heap count includes stale entries and is maintained across pushes, pops, redistribution and clears; overflow-checked property tests covered 450,000 interleaved operations against a binary heap and an additional 150,000 two-heap operations against a tree map.

The candidate matched all 16 full seed-1 runs on the shared dot VM, with median 0.61868 s versus 1.03817 s for the prior meeting-update source. Native VM time is not an official score. Independent checks passed 36,864 exhaustive small-graph queries, 16,000 random queries, a maximum-size maximum-weight chain and 6,000 repeated/unreachable queries, including overflow-checked and forced-worker builds. Reproducers, prior source and ARM measurements are in `experiments/track-d-balanced-frontier/`. At d144adc, the prior implementation passed every official practice gate in `run-1d5819c1f8db`, T=0.701512 s, M=455,716,864 bytes, S=236, K=9.020576 (`experiments/board-d144.json`). The official board must measure this candidate's own time, memory and source count.

Official practice `run-c30f8b29945f` at 073646e passed every gate: T=0.383672 s, M=444,030,976 bytes, S=246, K=12.184975. The previous run measured T=0.701512 s and K=9.020576. These separate single public-seed runs are not final holdout scoring; see `experiments/board-073.json`.

## Transparent hugepage hint

The isolated candidate requests optional `MADV_HUGEPAGE` on complete 4 KiB pages wholly inside each worker-owned distance vector, ignores any advice failure and otherwise retains the exact graph algorithm. Independent review and simulated failure/range tests found no safety defect for the official x86-64 environment. On the parent-run shared x86 dot VM, paired warm-data wall time was 34–39% lower and CPU 36–40% lower, with similar median process RSS. A standalone diagnostic confirmed advice success and 24 MiB actual hugepage backing versus none for baseline. Across this and four other experiments, 272 full hashes, 40 alternate comparisons, AVX2/guard, collision and graph-oracle checks passed. The result depends on kernel THP policy; the hint may be ignored, and native process RSS is not official cgroup peak. The previous implementation is `experiments/track-d-thp/baseline.rs`; official practice validation follows below.

Official public-seed practice `run-fdfb7cc11c20` at `bc902c7fdd8fede571eb40f9dc673e182d81fdb0` passed all gates: T=0.457316 s, M=444,346,368 bytes, S=260, D=1, K=11.066979. The preceding baseline batch `run-a7a238d889a1` was T=0.374915 s, M=444,428,288 bytes, S=246 and K=12.324253. These are separate batches, and C also varied markedly in the newer batch; official THP behavior is unknown. A same-code repeat follows below. See `experiments/board-bc902.json`.

The same-code official repeat `run-d8475ad31592` at `8094a4d6024565793d6d8eaf4bf30c794dd5f42a` passed all gates but measured T=0.400150 s, M=444,502,016 bytes, S=260 and K=11.830292. Both THP batches were slower than the earlier 0.374915 s baseline batch; earlier baseline runs also measured 0.367311 and 0.376725 s. The actual official kernel THP behavior is unknown and separate batches can vary, but the no-hint source was restored for the speed-first objective. The THP candidate and VM evidence remain in `experiments/track-d-thp/`; all track results are in `experiments/board-8094.json`.

The restored no-hint source then passed all official gates at `451429c73448bd439e4aeb871ab2fba936b08a97`, run `run-2856e0ff0d9f`: T=0.374698 s, M=444,792,832 bytes, S=246, D=1, K=12.325800. This separate batch supports the rollback; timing varies between batches and the official hugepage policy remains unknown. The four track results are recorded in `experiments/board-451429.json`.
