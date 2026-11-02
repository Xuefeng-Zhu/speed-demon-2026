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

## Read-only graph mapping

The isolated candidate replaces each worker’s positioned-read copy of the immutable graph with a read-only private mapping and parses the same line-aligned ranges. It retains the no-THP distance arrays. Independent review found no defect under the stable read-only input contract; exact candidate tests passed 96,000 random-oracle queries at six worker counts, 36,864 exhaustive queries, maximum-weight and repeated-query cases, and 63 graph partition cases across seven worker counts. Parent-run native x86 VM paired batches reported 0.8–3.7% lower wall time with approximately 26% higher native process RSS. Across this, B grouped and C parser packages, 164 full hashes, 24 alternate references, guard-page, collision, boundary and graph-oracle checks passed. Mapping memory is charged differently from a positioned-read buffer in a prewarmed cgroup; official practice remains necessary. The prior source is `experiments/track-d-mmap-restored/baseline.rs`.

The first mapping practice `run-804aafa58842` at `a9e1d0d8d990e2950833800deca06fad779bc766` passed all gates: T=0.383379 s, M=445,329,408 bytes, S=252 and K=12.138558. The immediately preceding no-map batch `run-158b64d75087` was 0.377822 s, M=444,674,048 bytes, S=246 and K=12.275392. C was also unusually slow in the mapping batch despite unchanged C code. These separate batches do not establish a speed gain; a same-D-source repeat is being collected while testing the independent C change. See `experiments/board-a9e1.json`.

The same-D-source repeat `run-706eca0b1334` at `3ee91f3e4d992656829878b41a0ad5c317689a38` passed every gate, with T=0.463912 s, M=444,424,192 bytes, S=252 and K=11.039266. Both mapped batches (0.383379 and 0.463912 s) were slower than the earlier no-map batch at 0.377822 s; prior no-map batches were approximately 0.371–0.375 s. Separate runs vary, but no official speed win was established, so the positioned-read baseline was restored. The mapped source and VM evidence remain in `experiments/track-d-mmap-restored/`; all four results are in `experiments/board-3ee91.json`.

The positioned-read source was confirmed again at `b4f634be302b2044c10d748d2f9b7e446b818fdb`, run `run-90fac2a8a1fd`: all gates passed, T=0.370416 s, M=444,289,024 bytes, S=246 and K=12.399649. This supports the mapping rollback; see `experiments/board-b4f63.json`.

## Packed adjacency with exact wide-weight fallback

The selected trial stores a 21-bit node ID and 11-bit inline weight for graphs with at most 2^21 nodes; weight code 2047 reads the original u32 weight from a per-edge side array. Larger graphs use the original u64 CSR. Both arrays together still reserve eight bytes per edge: this is a locality and zero-page experiment, not a 50% adjacency allocation reduction. Original exact source and the trial are in `experiments/track-d-packed32-adj/`.

Independent parent-run x86 dot VM review found no concrete encoding or ownership defect; 72 full seed-1 output hashes, eight alternate references, directed graph oracles and extreme/fallback tests passed. Two native paired batches showed 1.5–1.6% lower wall, 0.7–0.9% lower CPU and 4.8–5.6% lower median process RSS. These small differences are not official scoring or cgroup measurements. A local overflow-checked build additionally passed 16,000 random Dijkstra queries and boundaries at 2^21 and 2^21+1 nodes with weights through u32::MAX. Official single-change practice is pending. The immediately preceding unchanged-source practice `run-86e4430249ae` at `801c3cccca6ab13f2b363132a3963f68dc75ed93` passed all gates at T=0.394493 s, M=443,904,000 bytes, S=246 and K=12.017383; earlier identical-code practice was 0.370193 s, showing material run variance. See `experiments/board-801c.json`.

The first official packed-adjacency practice `run-ded061256d7b` at `f7c90f611b3c6be32cdc0a62d6d8b1623877ddb0` passed all gates: T=0.374922 s, M=443,854,848 bytes, S=280 and K=12.090250. Immediately prior original-adjacency runs were 0.394493 and 0.370193 s; these are separate batches with material timing variation, so the small dot VM improvement is not established on the scoring box. A same-code repeat accompanies the next C trial. See `experiments/board-f7c9.json`.

The same packed-adjacency source passed all gates again in `run-0ca8c15607de` at `e1a69bebee9aafa73ba36b2ba5dfe0925e13ac3e`: T=0.359675 s, M=443,940,864 bytes, S=280 and K=12.343371. The first packed batch was 0.374922 s; earlier original-adjacency batches included 0.367035, 0.370193 and 0.394493 s with S=246. These independent practices vary, so a small improvement is not established; the packed source is provisionally retained for speed, with a further same-code repeat. The best original K remains 12.458512 versus the packed best 12.343371. See `experiments/board-e1a6.json`.

A third packed-adjacency practice `run-7c4c48f8dd92` at `5afd571bd74972556df0e445cba076176a8ab660` passed all gates: T=0.379161 s, M=442,712,064 bytes, S=280 and K=12.028676. Packed batch times are 0.374922, 0.359675 and 0.379161 s, versus earlier original-adjacency batches of 0.367035, 0.378145, 0.373647, 0.370193 and 0.394493 s. The spread overlaps and does not establish an official speed advantage. The paired x86 VM gain was only 1.5–1.6%; this trial is provisionally retained while the u32-distance candidate is tested against it, and the exact original remains available. See `experiments/board-5afd.json`.

## Capped narrow search with exact indexed fallback

The trial uses complemented u32 distance pairs and a fixed 65,536-node radix pool per direction. If a pool fills or an answer at or above u32::MAX may have been discarded, it clears the partial state and reruns the query using exact u64 distances and indexed radix queues with fixed per-vertex link arrays. Up to 12 workers are used. This preserves large weights, cutoff cases and arbitrary valid directed graphs; the previous exact source is `experiments/track-d-capped-hybrid/packed.rs`.

Independent static reviews, a million-operation queue model, forced pool capacities 0/1/2/default, 15,000 alternating cleanup/fallback queries, actual 65,536-node fill/refuse/pop/refill tests, 16,000 randomized and 36,864 exhaustive answers, large-weight chains and repeated/unreachable tests found no defect. Parent-run native x86 dot VM full-seed comparisons were 15.0–17.7% faster than the packed baseline; across packages 252 full hashes and 24 alternate references passed. Instrumentation found no default-pool exhaustion and five wide-state allocations on public seed 1; a synthetic broad-frontier stress exhausted the pool 80 times and remained correct. A separate 12-worker fallback stress reported approximately 927 MiB process RSS versus 362 MiB for packed, not an official cgroup measurement.

An independent conditional accounting requests about 1.028 GB of search payload if all 12 workers retain both search states, and about 2.265 GB for the conservatively summed listed search, loader, graph/cache and stack payloads. It relies on allocator and loader-growth assumptions and omits unspecified kernel/runtime/cgroup charges; **it is not a formal 8 GiB worst-case proof**. The user prioritizes speed and authorized a reversible official practice when sufficiently safe; the bounded queues, wide margin in this conditional accounting, independent review and VM stress support testing the exact candidate, with the packed source available for rollback. Official results and parent-cgroup peak are pending; see `experiments/track-d-capped-hybrid/README.md` and `experiments/track-d-indexed-memory-bound/README.md`.

The first official hybrid practice `run-c008469037cd` at `2d67ab52cd4d32b95e806cf9e80ebfbc5102d544` passed every gate: T=0.348043 s, parent-cgroup M=438,562,816 bytes, S=528 and K=11.436937. Previous packed batches were 0.374922, 0.359675, 0.379161, 0.380508 and 0.382870 s with S=280; their best K was 12.343371 (the older unpacked baseline best was 12.458512). These unpaired official practices vary, and the hybrid's substantially larger source reduces K despite its fastest recorded wall time. It remains selected provisionally under the explicit speed-first objective, with a same-code repeat pending and the exact packed source preserved. The single public-seed cgroup peak does not prove an 8 GiB worst-case bound. See `experiments/board-2d67.json`.

The same hybrid source passed all gates again in `run-a079e020de30` at `7caf8a4b7580cd8668b6302b7d8afdd469bb0640`: T=0.343775 s, parent-cgroup M=413,552,640 bytes, S=528 and K=11.643652. Hybrid official batches were 0.348043 and 0.343775 s; earlier packed batches ranged 0.359675–0.382870 s. These are separate public-seed practices, not paired measurements or a hidden-data memory proof. They and the paired x86 VM runs support retaining the hybrid for wall speed, while its K remains below the best packed and unpacked recorded values (12.343371 and 12.458512). See `experiments/board-7caf.json`.

The same selected hybrid passed all gates again in `run-95677e859e5a` at `f4419112e1a07a7f3b73e1ee4580517b0bbf1597`: T=0.346533 s, M=465,305,600 bytes, S=528 and K=11.326940. Official public-seed hybrid peaks have varied; none proves the hidden-data cgroup maximum. See `experiments/board-f441.json`.

## Equal-minimum batches

This single-change trial pops at most sixteen entries from the chosen side's current minimum bucket before reevaluating frontier sizes and the stopping bound. Every batched entry has the same minimum key; delaying a stop may do extra work but cannot omit a shorter path. Existing stale-entry checks, cutoff detection, pool exhaustion cleanup and indexed-wide rerun remain. Additional work may alter which hidden queries exhaust a pool and trigger fallback, so the full 8 GiB cgroup bound remains unproved. The exact prior selected hybrid is `experiments/track-d-hybrid-samekey15/baseline.rs`.

Independent review and instrumented tests covered 18,012 adversarial answers with 233,324 actual later-in-batch pops. Both batch4 and batch16 passed 16,000 random and 36,864 exhaustive graph answers per each of seven forced capacities, threshold/node/max-weight/repeated queries, and actual exhaustion cleanup. Parent-run shared x86 dot VM paired full-seed testing found batch16 2.4–5.3% lower wall and 3.9–4.6% lower CPU than exact hybrid; batch4 gained less. Across the D, A and B packages, 308 full hashes, 28 alternate references, 48 all-escape runs and actual ISA/guard/fallback tests passed. Native VM figures are not official scoring-box or cgroup measurements. The prior same-code hybrid practice `run-95677e859e5a` at `f4419112e1a07a7f3b73e1ee4580517b0bbf1597` passed all gates at T=0.346533 s, M=465,305,600 bytes, S=528, K=11.326940. Official single-change practice is pending.

The first batch16 official practice `run-92d889391784` at `bce4da4e936059748493efd8b03b339902ce7489` passed every gate: T=0.365581 s, M=440,041,472 bytes, S=533 and K=11.135969. The immediately prior unbatched hybrid practices included 0.343775, 0.346206 and 0.346533 s with S=528. Separate batches vary and this observation conflicts with the two paired x86 VM improvements; the same D source will be repeated with the next A-only trial before deciding. See `experiments/board-bce4.json`.

Official practice `5e32c97` repeated exactly the `bce4da4` batch16 source: run `run-e3b9d011a2c0`, all gates passed, T=0.341423 s, parent cgroup peak 466,526,208 B, S=533, K=11.389298. The prior batch16 run was 0.365581 s; earlier unbatched hybrid runs were 0.343775–0.346533 s. This variance prevents a confident small speed comparison from these unpaired runs; VM paired trials favored batch16 2.4–5.3%. These public-seed cgroup results do not bound hidden-input memory; see `experiments/board-5e32.json`.

Another exact batch16 repeat at `a4e80b3`, `run-c71f8336d247`, passed all gates: T=0.340624 s, M=438,947,840 bytes, S=533, K=11.542459. Together the three batch16 batches are 0.365581, 0.341423 and 0.340624 s; previous unbatched hybrid batches included 0.343775, 0.346206 and 0.346533 s. Paired VM evidence favors batching, and the later target batches are consistent with a small win; practice variation means the exact magnitude is uncertain. Retain batch16 under the speed-first objective. The hidden-input cgroup peak remains unproved. See `experiments/board-a4e80.json`.

At `c0a5426` the unchanged batch16 source passed all official gates in `run-b80700104382`, T=0.365618 s, M=439,451,648 bytes, S=533, K=11.138393. This is a fourth separate practice batch (0.365581, 0.341423, 0.340624, 0.365618 s); the spread limits target-machine conclusions on a small gain. Paired VM trials favored batch16; the hidden-data parent-cgroup maximum remains unproved. See `experiments/board-c0a5426.json`.

## Coarse distance buckets

The candidate groups narrow queue keys by `distance >> 6` while retaining exact distances and enqueuing every strict improvement, including re-expansions. Bucket starts are conservative lower bounds for the bidirectional stop; processing cannot advance a bucket until it is drained. Capacity exhaustion and narrow cutoffs retain the existing cleared-state exact wide fallback. Independent review found no concrete correctness defect, and seven capacity configurations passed 16,000 random and 36,864 exhaustive graph queries each, including cutoff, packed/wide and extreme bounds. Dense directed zero/parallel tests exercised 4,738,464 repeat expansions and 1,039,433 inverted exact-key pops; an 8,191-node same-bucket case exercised actual exhaustion and fallback. See `experiments/track-d-coarse-buckets24/` for source, proof argument, tests and exact previous source.

Parent-run native x86 dot VM two 17-pair batches measured 5.9% and 8.4% lower wall, 8.9% and 9.4% lower CPU; 72 full-seed hashes and additional forced-capacity/oracle/extreme checks passed. Coarse ordering may increase repeated work and trigger more exact fallbacks. The fixed queue sizes are unchanged but whole-container hidden-input 8 GiB cgroup safety remains conditional, not formally proven. These native results are not an official score; a reversible target practice follows.

The first coarse-bucket target practice `run-1ec79b1bffc8` at `5a41a4b` passed all gates: T=0.321238 s, parent-cgroup M=467,632,128 bytes, S=535 and K=11.729520. The immediately preceding unmodified batch16 practice was 0.345496 s; other previous batch16 practices spanned 0.339438–0.423655 s. These independent batches vary, so repeat the same candidate before quantifying a target gain. This public-seed cgroup observation does not prove a hidden-data memory bound. See `experiments/board-5a41.json`.

The same coarse-bucket source passed all gates again at `437715c`, `run-5f1161483b80`: T=0.313420 s, M=438,222,848 bytes, S=535, K=12.030182. The two target batches are 0.321238 and 0.313420 s versus previous batch16 samples 0.339438–0.423655 s. Although independent practice batches vary, these measurements and the paired VM tests support retaining coarse buckets for wall speed. This public-seed cgroup peak does not establish hidden-data 8 GiB safety. See `experiments/board-437715.json`.

## Forward pruning against the reverse lower bound

This reversible single-source trial leaves reverse search unpruned. For a forward relaxation, if its exact distance plus the reverse minimum bucket start cannot beat the current best, it first considers any known reverse label at the destination and then skips that relaxation. Lower reverse buckets have drained; an unknown reverse distance is at least the conservative bound. Narrow cutoffs, fixed pools and the cleared-state exact wide fallback are unchanged. The previous source is `experiments/track-d-coarse-forward-prune29/baseline.rs`.

Independent review found no concrete defect. Seven forced capacities passed random, exhaustive, cutoff, packed/wide and chain cases; independent small-graph oracles, dense zero-weight/parallel graphs and actual exhaustion passed. A targeted eight-edge fixture in `experiments/d-prune-meeting-review30/` exercises an actual before-prune meeting improvement above the narrow cutoff, with exact wide rerun matching an independent oracle. Two million graphs and ten million queries found 206 branch hits and no improvement value below the cutoff; that finite search is not a proof. Keep the explicit meeting check. Parent-run native x86 paired tests measured 1.8% and 2.9% lower wall with mixed CPU and similar native RSS; across diagnostics and candidate, 88 full hashes and alternate/oracle/fallback tests passed. This is not official scoring, and the hidden-data 8 GiB parent-cgroup bound remains unproved. A target practice follows.

The first forward-prune official practice `run-018e111722fb` at `bd1301f` passed all gates: T=0.331110 s, M=438,083,584 bytes, S=542, K=11.682349. The immediately preceding unpruned coarse batch was 0.333954 s; earlier unpruned batches included 0.313420, 0.321238 and 0.315454 s. Independent batches vary and this one does not establish the small target gain seen in paired VM testing. Repeat exact candidate before deciding; the public-seed cgroup peak does not prove hidden-data 8 GiB safety. See `experiments/board-bd130.json`.

The same forward-prune candidate passed all gates again at `a3bc44f`, `run-c2cd58b58dc8`, T=0.352635 s. Its official batches were 0.331110 and 0.352635 s versus prior unpruned coarse batches of 0.313420, 0.321238, 0.315454 and 0.333954 s; the extra source also raised S from 535 to 542. Despite the small paired VM win, independent official batches did not show a target gain. Restore the exact unpruned source for a single-change practice comparison; keep the candidate and branch regression for future experiments. This does not establish a hidden-input cgroup bound. See `experiments/board-a3bc.json`.

The restored unpruned coarse source passed all gates at `386aec0`, `run-4ca1789c24ea`, T=0.334935 s. This is close to the first forward-prune batch of 0.331110 s and faster than its second of 0.352635 s, while earlier unpruned batches were 0.313420–0.333954 s. Independent batches vary, and the small paired VM improvement has not been reproduced consistently on target, so retain the simpler unpruned source. The snapshot `experiments/board-386aec.json` has the authoritative run ID and all axes; these public-seed observations do not prove hidden-data cgroup safety.

## Merge of speed-opt source (2026-10-31)

`src/main.rs` replaced with the `speed-opt` version (Dockerfile, .speed-demon.toml and build flags unchanged). Sandbox A/B against `3b1126e` on full seed 1 (2-core arm64, noisy, min of alternating runs, hashes match): no official board run yet for this source. Add the run ID here once the board has scored it, and revert to `3b1126e` if the board T is not better.
Sandbox CPU min: 2.33 s -> 1.54 s; sandbox peak RSS at 2 threads rose ~195 -> 241 MB (includes mmap pages), so check board M.

## Round 2: packed u32 edges (2026-10-31)

Edges packed as one u32 (21-bit node, 11-bit weight; large weights in a sorted side list), single parse to u64 per edge then per-block build, old graph freed before the backward graph, u32 distances with exact u64 rerun when needed, compare_exchange cluster claim. Board `run-d1fea4ee2487` at `ccbfbc0`: T=0.185344 s, M=87.7 MB, S=390, K=22.63 (was 18.94). Kept.

Round-3 trial (cand1): renumbering writes renumbered rows directly (one atomic reserves ids + edge slots per cluster), zeroed rank array, parallel prefix sums, exit right after write, 8-byte heap entries (low 32 bits of key), separate forward/backward distance pools, u16 block map.

## Round 3: coarse radix keys (2026-10-31)

The speed-opt rewrite had dropped coarse buckets. Both search queues are now keyed by `distance >> 6` while storing exact distances; a popped node is expanded with its current distance unless that distance lies in an earlier bucket, and the stop test uses bucket starts as lower bounds. A sandbox phase profile of the previous source (8 cores) showed parse 30 ms, renumber 30 ms, relabel 24 ms and queries 103 ms. On the same sandbox, 21 alternating full-seed runs measured 183.5 ms median against 199.1 ms for `dddc0ea`; the full hash, random/exhaustive/boundary/extreme oracles and a new same-bucket stress passed. Sandbox times are not board results. Details and the previous source: `experiments/track-d-coarse-radix33/`. Board run pending.

## Round 3: prefetch in the renumbering BFS (2026-10-31, reverted)

The clustering BFS prefetched the row bounds, rows and head claim slots of nodes queued 16, 8 and 4 places ahead (`dbab6be`). In 25 alternating sandbox runs the median went from 185.8 ms to 178.7 ms.

Board run `run-da3a65ce91e2` at `dbab6be` (pushed 15:19 PDT, scored before 15:34 PDT): T=0.1682 s, S=410, K=23.72; M was not recorded. That commit also contains round-3 cand1 (`1609923`) and coarse radix keys (`963a9e5`), neither of which has its own board run, so the gain over the previous recorded run (`run-d1fea4ee2487` at `ccbfbc0`: T=0.185344 s, S=390, K=22.63) cannot be split between the three changes. The same batch scored A `run-33ec536bde8b` (K 39.20), B `run-17bdd855bde2` (K 22.79) and C `run-24986b362ab9` (K 28.76). The BFS prefetch was reverted in `b607e9e`; no reason was recorded. Its source and experiment folder remain in `dbab6be`.

## Round 3: prefetch the next pops in the query loop (2026-10-31)

Applied on top of `b607e9e` (coarse keys, no BFS prefetch). After each pop the search prefetches the row bounds of the second-next entry and the adjacency row of the next entry in the same side's minimum bucket. In one batch of 25 alternating sandbox runs on full seed 1: `b607e9e` 188.0 ms median, this change 175.3 ms, and this change plus the reverted BFS prefetch 170.6 ms. The full hash and all oracle suites passed. A third stage that also prefetched the neighbours' distance slots was slower. Dynamic parse chunks and `MAP_POPULATE` were neutral or slower and were not kept. Sandbox times are not board results. Details: `experiments/track-d-query-prefetch37/`.

Board run `run-8fefae2c6482` at `804a03c`: T=163.10 ms, S=407, against 168.2 ms and S=410 for `dbab6be`. Two later board runs of the same D source measured 166.50 and 165.81 ms (run IDs not recorded), so the three-run mean is about 165.1 ms, about 2% faster than `dbab6be` with 3 fewer lines. Kept.

## Round 3: query-phase screens (2026-10-31, none kept)

On `804a03c`, `SHIFT` 5 and 7, four other prefetch distances, a ring bucket queue in place of the radix heap, distances carried in heap entries, and expanding one side 8 or 16 times in a row were all neutral (within 1–2 ms of noise) or slower in the sandbox. Cycle timers put 45% of query-loop time in edge relaxation and 16% in queue `top()`. Same-distance repeat expansions are 3.3% of expansions. Query time was the same (83–90 ms) under four node orderings, including one whole-graph BFS, so renumbering locality is saturated. Details: `experiments/track-d-query-screens38/`.

## Round 3: line trim (2026-10-31)

Board S matches default-rustfmt code lines of `main.rs` plus the 7 Dockerfile lines for `ccbfbc0`, `dbab6be` and `804a03c` (390, 410, 407); this is inferred, not documented. The old source had eight lines that rustfmt splits, which cost 22 lines. The source is now rustfmt-formatted, `each_edge` is inlined, `claim` uses `fetch_max(1)`, and a few expressions are named, so they fit on one line. Formatted code lines went from 400 to 376, so expected S is about 383 (+0.9% K). Behaviour is unchanged: the full hash and all oracle suites passed, and 25 alternating sandbox runs measured 175.6 ms against 175.5 ms. Details: `experiments/track-d-line-trim39/`.

Board run at `97df345` (run ID not recorded): S=383, as predicted, which confirms the S rule above. T=169 ms and K=23.93, against the best D K of 24.11 (T=163.10 ms, S=407). Same-code A and C scores in that batch were also below their bests, so the slower T looks like board noise. At equal T the K model gives 24.11 × (407/383)^0.15 ≈ 24.33; with T=169 ms it gives 23.90, close to the measured 23.93.

## Round 3: BFS row prefetch, re-screened (2026-10-31)

The reverted three-stage BFS prefetch was re-screened stage by stage on `97df345` (`experiments/track-d-bfs-row-prefetch40/`). Prefetching the adjacency row of the node eight places ahead in the clustering BFS carries the gain; prefetching the row bounds and the claim slots adds lines without a reliable extra gain. The selected one-stage version adds 3 counted lines (expected S about 386). In 31 alternating sandbox runs it measured 167.4 ms median against 174.7 ms for `97df345`; the full hash and all oracle suites passed. Sandbox times are not board results.

Board run at `7b43b63` (run ID not recorded): T=160 ms, K=24.50, a new D best (previous best K=24.11 at T=163.10 ms, S=407). The K model predicts 24.11 × (163.10/160)^0.5 × (407/386)^0.15 ≈ 24.54 if S=386, as expected; board S was not recorded.

## Round 3: persistent worker threads (2026-10-31, not kept)

Spawning and joining the worker threads costs about 0.2 ms per `parallel` call in the sandbox. A persistent channel-fed pool measured 171.0 ms median against 169.5 ms over 31 alternating runs (no measurable gain) and adds 22 counted lines, about −0.8% K. Details: `experiments/track-d-thread-pool41/`.


Board trial, 1 Nov 2026: PR #27 (`d-mem`, two-pass CSR from mmap, S 416) ran `run-a9c0c5ffe415` at `aa5ab52` (T=175.3 ms, M=74.8 MB, K=23.79). It is inside production's same-code range (23.6 to 24.3) and below the 24.50 best, so it was not kept. Production D in the same window: K 23.77, 24.05, 24.21, 23.73.

- Nov 1 2026: PR #36 half-side CSR on THP-fixed D, d5efd3a run-245c4954b6f9 T 154.2 ms M 74.7 MB S 406 K 25.46 < 26.53 (M rose on board). Reverted.
- Nov 1 2026: PR #42 d-reuse-spare cb9c687 run-012cda1c4d0c T 142.2 ms M 87.1 MB S 389 K 25.88 (run 1; M spike like production noise 69-87 MB).
- Nov 1 2026: PR #42 run 2 7af73b3 run-3761681eb879 T 150.2 ms M 71.0 MB S 389 K 26.23. Mean 26.06 vs same-code production ~25.6 (range 25.0-26.7). Kept (structural: fewer serial huge-page faults, S unchanged).
- Nov 1 2026: build-time PGO (Dockerfile stage, sample seed 2, +19 S). c3c3056 run-d60644be17aa T 138.2 ms M 71.9 MB S 408 K 27.08; 58f702e run-9483b5685af5 T 141.6 M 72.0 K 26.75; 5530ffa run-6b6f46ded213 T 150.8 M 72.0 K 25.93. Mean 26.59 = production (~26.6). Not kept.
- Nov 1 2026: PR #53 run 1, 9120151 run-d504d41a9dd3 T 141.1 ms M 70.7 MB S 392 K 27.05 (same batch A 40.63 a bit slow).
- Nov 1 2026: PR #53 run 2, 9d3af37 run-911736f103f5 T 141.6 ms M 70.9 MB S 392 K 26.99. Runs 27.05/26.99 (mean 27.02, T ~141) vs recent #42 runs 26.96/26.70/26.12 (T 142.6-150.5): KEPT. Production D src = PR #53 head 545c5fe.
