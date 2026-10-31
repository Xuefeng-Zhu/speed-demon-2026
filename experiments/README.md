# Local optimization experiments

These measurements are for iteration, not official scores. All benchmarks used seed-1 full data, native macOS ARM builds, one warmup per variant, then five measured runs per variant. `benchmark.py` interleaves order, deletes the prior output, and checks every output against the official full SHA-256. No other candidate experiments were deliberately running during these comparisons. Uncontrolled system activity, cache behavior, compiler differences and CPU architecture still limit transfer to the x86 judging machine. See the JSON reports for each timing and exact binary invocation.

| Track | Baseline median | Candidate median | Local median ratio |
|---|---:|---:|---:|
| A: original vs chunked/select | 0.365936 s | 0.244733 s | 1.50× faster |
| B: original vs token views | 3.612033 s | 3.118447 s | 1.16× faster |
| C: original vs prior serial input views | 2.636044 s | 1.499528 s | 1.76× faster |
| D: 12 vs 6 workers | 1.018773 s | 1.102140 s | 6 workers 8.2% slower |
| D: 6 vs 3 workers | 1.110951 s | 1.422599 s | 3 workers 28.1% slower |

For D, a separate earlier local per-process measurement recorded roughly 766 MB peak RSS for 12 workers and 515 MB for 6; 3 used around 381–388 MB in a noisy run. Six is a provisional compromise because memory also contributes to the score. These macOS RSS values and times are not the judge's cgroup memory or execution measurements; confirm the worker choice on the board.

For the earlier comparisons, compile A–C using `c++ -std=c++17 -O3 -DNDEBUG -pthread` for both the preserved original `track-<letter>-agent/main.cpp` and current `track-<letter>/main.cpp`. D's baseline reconstruction is in `track-d/PERF.md`. The corresponding JSON files contain all measurements and exact arguments. `/tmp` paths refer to locally generated inputs, and can be recreated with the official generators. Example for A after compiling:

```sh
python3 experiments/benchmark.py --baseline '/tmp/speed-bench/a-old /tmp/speed-demon-a-full/requests.log /tmp/speed-bench/a.txt' --candidate '/tmp/speed-bench/a-new /tmp/speed-demon-a-full/requests.log /tmp/speed-bench/a.txt' --output /tmp/speed-bench/a.txt --expected 495ca09682b9673ef836a506496177680bb4a3af54255174befddb1f83481cd3 --runs 5 --report experiments/bench-a.json
```

`differential.py` compiles the current candidate sources, generates inputs, runs the official reference, and compares bytes. Three tiny seeds (2, 17, 4242) passed for all four tracks; JSON reports retain their hashes. The separate `a_chunk_boundaries.py` test passed nine deliberately placed 1 MiB splits spanning a maximum-length log line. `x86.md` records the non-destructive x86 sample checks.

## Additional experiments

`a-output-buffered.cpp` matched full seed 1, seed 999 sample, and independent synthetic tests; an eight-pair native Mac experiment suggested a roughly 7% trimmed-mean improvement. `b-zero-copy.cpp` matched full seed 1 and alternate-seed/randomized tests; an initial 17% native median improvement was against an older baseline, and later contended tests against the current candidate did not show a reliable advantage. `track-d-sparse/src/main.rs` matched full seed 1, with similar local speed and lower observed memory in three pairs. These are experimental alternatives, not the selected submissions; their x86 and competition-container performance and scoring effects remain unverified. See the accompanying reports where present.

The subsequent native x86 dot VM comparison of A–C is recorded in `dot-vm.md`.


## October 31 follow-up variants

`c-parallel.cpp` is an experimental C variant that sorts and deduplicates independent country groups with six worker threads. It matched the full seed-1 output hash in five benchmark runs and in a restricted ARM Linux Docker run; sample seed 42 and tiny seeds 2, 3, 17, 99 and 12345 matched freshly generated official reference outputs. Five interleaved native Mac runs produced median wall times of 0.794665 s for the prior serial candidate and 0.408305 s for the variant; other processes were active. Full samples are in `bench-c-parallel.json`. Compile both with `c++ -std=c++17 -O3 -DNDEBUG -pthread`. The variant subsequently passed native x86 comparisons and was promoted to `track-c/main.cpp`; see `dot-vm.md`. Official cgroup memory and source-size scoring effects remain unmeasured. The prior serial source is preserved in `c-serial.cpp`.

The selected dense Track D and experimental sparse variant both passed 16,000 queries over 80 randomized directed graphs against an independent Python Dijkstra oracle, including zero and uint32-max weights and unreachable paths. `d_random_review.py` accepts one or more compiled executable paths to reproduce this check. Five interleaved full seed-1 native Mac runs produced medians of 2.336 s dense and 2.441 s sparse, with substantial concurrent system activity; every hash matched the published answer. See `bench-d-review.json`. The sparse variant's x86 and cgroup memory measurements remain outstanding, so the selected implementation is unchanged.

## Additional isolated variants

These variants were experimental when written; `track-d-seen16` has since been selected. They still need official scoring-machine measurements. Local timings used macOS ARM while other work was active; peak RSS is not competition cgroup memory.

- `a-parallel-output.cpp`: six parallel hour workers with output buffering. Five paired full seed-1 runs had medians 0.2142 s versus 0.2620 s current, each matching the published hash. One peak RSS observation was 39.8 MB versus 27.8 MB. Sample seed 999, nine chunk boundaries and four synthetic differential cases passed. With those local time and single RSS observations, the time/memory K factors favor the variant by about 2.9% before source-size effects. Compile with `c++ -std=c++17 -O3 -DNDEBUG -pthread`; see `bench-a-parallel-output.json`.
- `b-parallel-query.cpp`: six workers evaluate independent queries into indexed output slots. Three paired full seed-1 runs had medians 3.571 s versus 7.503 s for the then-selected candidate, with all hashes matching. Other work was running and timing varied widely. Sample seeds 13, 42 and 76543, tiny seeds 2, 17, 99 and 4242, and a 1,000-query edge fixture matched the official reference. It also passed an offline restricted ARM Linux Docker full-data hash check with `-pthread`. Reproduce the fixture with `python3 experiments/b-edge-fixture.py /path/to/binary official/reference/b_index.py`. Compile with `c++ -std=c++17 -O3 -DNDEBUG -pthread`; see `bench-b-parallel-query.json`.
- `track-d-seen16/`: changes per-worker visit epochs to u16 and clears tags before epoch wrap. Five paired full seed-1 runs had medians 1.477 s versus 1.532 s for the prior dense candidate; every hash matched. Separate single RSS observations were 472.7 MB versus 513.2 MB. It passed 16,000 randomized Dijkstra queries and a 65,540-query single-worker wraparound check. Build with `cargo build --release --offline --manifest-path experiments/track-d-seen16/Cargo.toml`; see `bench-d-seen16.json`.


## Reproducible native comparisons

`compare-variants.py` compiles the selected candidate and one named variant with the same flags, warms each, interleaves runs, verifies every output SHA-256, and writes wall time, CPU time, per-process peak RSS, compiler and source hashes to JSON. It is a local iteration tool; RSS is not cgroup memory and elapsed time includes process startup. Use Python 3.11+, an existing generated dataset, C++17 or Rust as appropriate. Linux `ru_maxrss` is KiB, while macOS uses bytes. For the published full seed-1 data, for example:

```sh
python3 experiments/compare-variants.py b parallel --data /path/to/b-full --report /tmp/b-comparison.json
python3 experiments/compare-variants.py b parallel-index --baseline-variant parallel --data /path/to/b-full --report /tmp/b-index-comparison.json
python3 experiments/compare-variants.py a buffered --data /path/to/a-full --report /tmp/a-buffered.json
python3 experiments/compare-variants.py a parallel --data /path/to/a-full --report /tmp/a-parallel.json
python3 experiments/compare-variants.py d dense --data /path/to/d-full --report /tmp/d-dense.json
python3 experiments/compare-variants.py d sparse --data /path/to/d-full --report /tmp/d-sparse.json
python3 experiments/compare-variants.py d packed --data /path/to/d-full --report /tmp/d-packed.json
```

Other dataset scales and seeds need their own correct hash supplied with `--expected`. Run comparisons without other load and retain all runs; they do not replace the official harness or its five-run scoring procedure. A subsequent six-run Mac rotation produced medians of 0.3133 s selected, 0.2896 s buffered, and 0.2520 s parallel for full Track A; every output matched the published hash. Other jobs were active. Raw results are in `bench-a-rotation.json`.


## New x86 candidates

`b-parallel-index.cpp` adds six-worker mmap corpus indexing to the parallel-query variant. Five local full-data pairs had medians of 2.916 s versus 4.247 s for parallel queries alone; every result matched the published hash. Sample seed 13, tiny seeds 2, 17, 99 and 4242, and the 1,000-query edge fixture matched the reference. Separate single-process peak RSS observations were about 728 MB versus 369 MB, so those noisy local time and memory factors suggest only ~1.05× K before source-size effects. Neither x86 nor restricted-container validation has been completed for this indexing variant. See `bench-b-parallel-index.json`; compare it directly against `parallel` with the command above.

`track-d-packed/` combines a 53-bit distance with an 11-bit visit epoch. Five local full-data pairs had medians 1.714 s packed versus 2.144 s for the then-selected dense candidate; all output hashes matched. Three separate packed RSS observations were 356.7–430.9 MB versus 492.0–513.7 MB for that dense candidate. All tests and measurements are described in its README and JSON files. Packing relies on the official full-scale 1,740,512-node bound; an independent review found the bound sufficient for each tentative relaxation and epoch reset, but the implementation needs a fallback before it can safely handle larger graphs. The experiment is not yet checked on x86 or in the official container.

## Follow-up: Track C delimiter scan (not adopted)

`c-strchr.cpp` replaces per-byte CSV delimiter scans with libc `strchr`. Every full seed-1 output matched the published hash in warmups and five paired native Mac runs. The current candidate had median wall time 0.364963 s versus 0.387789 s for this variant (0.94×), with other activity possible. The source and all timings are retained in `bench-c-strchr.json`; the variant was not adopted and has not been measured on x86 or the official harness.


## Follow-up indexing and graph experiments

`b-stream-index.cpp` uses bounded `pread` buffers instead of mmap in the parallel indexer. Five paired ARM Mac full-data runs all matched the published hash; medians were 1.364 s stream versus 1.590 s mmap, with maximum observed per-process RSS 489,553,920 versus 726,466,560 bytes. Other work was active. Sample seeds 1 and 13, tiny seed 99, and the 1,000-query edge fixture matched their reference. See `bench-b-stream-index.json`. The variant also passed a pinned offline ARM Linux restricted-container run on full data. It was subsequently x86-tested and selected; see `dot-vm.md`. It has not been measured on the official scoring box. Run `python3 experiments/compare-variants.py b stream-index --baseline-variant parallel-index --data /path/to/b-full --report /tmp/b-stream.json`.

`track-d-packed-u32/` reduces packed-search CSR offsets to u32. It matched all full-data hashes and 16,000 independent randomized oracle queries, but three paired local medians were 1.484 s versus 1.327 s for packed baseline, with separate single RSS observations of 423,919,616 versus 430,309,376 bytes. The small memory saving did not justify promotion on these contended, non-official observations. Raw timings are in `bench-d-packed-u32.json`.


`c-hashsort.cpp` caches a hash per name and resolves collisions with the full string. Five paired local full-data runs all matched the published hash; selected median was 0.698572 s versus 0.645820 s for this variant under concurrent activity. Sample seed 42 matched the official reference; a forced constant-hash build also matched, exercising collision handling. Separate process RSS observations were 293–299 MB selected versus 312–330 MB hash-sort. This modest and noisy time gain comes with higher memory and source size; it remains experimental. See `bench-c-hashsort.json` and `rss-c-hashsort.json`.

`b-phrase-intersect.cpp` adds phrase-postings intersection. Three completed, noisy paired runs produced medians of 3.718 s variant versus 3.598 s baseline; hashes and the edge fixture passed. It was not adopted, and further alternate-seed and x86 checks were not run. See `b-phrase-intersect-notes.md`.

`c-parallel-parse.cpp` splits CSV parsing among six workers at quote-aware record boundaries. Five local full-data pairs produced 0.347339 s variant versus 0.338932 s selected, all matching the published hash; sample seed 42 matched the reference. The small loss and additional boundary complexity did not justify promotion. It has not been exhaustively tested or measured on x86; see `bench-c-parallel-parse.json`.


## Further local iteration

`a-striped.cpp` divides the log at complete-line boundaries across six workers, parses worker-local groups, and merges them. Five paired ARM Mac runs under shared load had median time/RSS of 0.148553 s / 59,326,464 B striped versus 0.273756 s / 27,754,496 B selected; the time and memory terms imply ~1.166× K before source-size effects. The variant matched the published full hash in a restricted ARM Docker run; sample seeds 2, 13, 999 and 76543 matched the reference, and synthetic and nine read-boundary cases passed. See `bench-a-striped-rss.json` and `bench-a-striped.json`. It remains experimental pending x86 and official scoring.

For Track C, six rotated local full-data runs each produced median walls 0.435599 s with 3 sort workers, 0.382468 s with 6, and 0.365818 s with 12. Maximum per-process RSS values were 293,437,440, 293,797,888, and 295,469,056 bytes, respectively; every hash matched, with possible contention. `c-workers-3.cpp`, `c-workers-12.cpp`, and `bench-c-workers.json` preserve the experiment. The selected six workers remain unchanged pending x86 and official checks.


## Local decisions after f45c4cf

A's three-shard buffered version was selected locally after the native x86 comparison and GCC warning review; the prior serial source is `a-serial-f45.cpp`. A later checked resize-and-copy merge was selected for explicit bounds and a warning-free GCC build; the insertion variant is preserved as `a-three-shard-insert.cpp` and the warning-free source as `a-three-shard-checked.cpp`. See `static-a-checked/`. At that stage C mmap and D parallel parsing remained experiments: using pinned formatter/scc counts and VM process measurements, their modeled K ratios were about 1.029 and 1.003, respectively. A later warm-cgroup comparison changed the C decision, as recorded below. Details are in `dot-vm.md`; pinned static-count evidence is in `static-f45/`, C mmap source, edge fixtures and measurements are in `c-mmap*`, and the D experiment and tests are in `track-d-parallel-parse/`.

A later Track B rare-anchor phrase experiment was about 2.1% slower than its zero-copy baseline on local full data. Local worker-count tests favored six workers over three and twelve; a 4 MiB read buffer's estimated 1.3% time/memory gain was too noisy to justify the extra memory. The failed/marginal experiments, commands, and data are in `b-iteration-summary.md` and matching sources and JSON files. The selected B remains unchanged.


## Warm-cache C cgroup comparison

A separate prewarmer container read both inputs and stayed alive while three restricted ARM Docker pairs ran, alternating order. All outputs matched the full hash. The heap-copy cgroup peaks were 277,241,856 / 276,971,520 / 277,200,896 B; mmap peaks were 75,550,720 / 76,128,256 / 75,730,944 B. The comparison reads each run container's `memory.peak` after the program exits but before the shell exits; shell/container overhead and ARM/OrbStack differ from the official parent-cgroup harness. This is local evidence, not a board score. See `c-cgroup-bench.py` and `c-cgroup-report.json`; input paths, images, and output folders in that script must be recreated. The host's official prewarming is documented in the competition context. Mmap was selected for board measurement; the heap baseline is `c-heap-664.cpp`.


## B bounded phrase summaries and C exact hash counting

The B bounded variant uses query-derived phrase anchors, deduplicates phrases and records bounded per-worker summaries instead of full match lists. It was x86-tested and selected; see `dot-vm.md`. `b-stream-2fc.cpp` preserves its board-tested predecessor. It passed an independent 40-corpus fuzz suite, a 250k-document/19k-duplicate-phrase stress, shard top-ten checks and the pinned ARM Docker full hash. It has not yet been measured on the board. See `b-bounded-*` and `bench-b-bounded.json`.

The C mmap+hash variant uses per-country open addressing and exact collision comparisons. It was independently reviewed, passed 40 mixed corpora with all hashes forced equal under ASan/UBSan, and was selected for board measurement. The comparison package's selected/mmap files were identical; distinguish its mmap baseline from the separate f45 heap comparison. `c-mmap-2fc.cpp` preserves the board-tested predecessor. See `c-hash-*` and `dot-vm.md`.

A separate quote-parallel parser is not selected. A repeated container invocation returned exit 1 without output; a shell-only control reproduced an output-directory ENOENT on the reused bind mount, although that does not prove the original cause. Against the current hash baseline on the shared ARM Mac, five native full-data pairs had medians 0.266 s baseline and 0.390 s quote-parallel, with noisy timings. Both matched the published full hash in every run and passed adversarial boundary tests. The earlier favorable comparison used the old sort baseline, not the current hash implementation.

## Official practice run for 02d7b4c

All four tracks passed every gate on the full public seed-1 dataset; raw run IDs and measurements are in `board-02d.json`. Compared with the preceding 2fc9110 practice run, B's measured time changed from 1.450775 to 1.837251 seconds, cgroup peak from 496,271,360 to 257,609,728 bytes, and K from 7.192344 to 6.994585. C's time changed from 0.527238 to 0.395185 seconds, peak from 76,075,008 to 81,285,120 bytes, and K from 6.548517 to 7.383038. These are separate official practice runs, not controlled paired measurements or final holdout scores. B's bounded summaries remain selected while faster bounded alternatives are investigated.

## Official practice run for 89795bb

All four tracks passed every gate on the full public seed-1 dataset; `board-897.json` records the run IDs and measurements. Relative to 02d7b4c, A's Rust implementation scored T=0.047542 s, M=48,148,480 bytes, S=273, K=27.939894 (previous K 13.101162); D's Rust implementation scored T=0.872892 s, M=453,419,008 bytes, S=233, K=8.110433 (previous K 6.382387). B and C code was unchanged, and their K values changed from 6.994585 to 7.665618 and 7.383038 to 7.446852 respectively. These are separate single public-seed practice runs; the final hidden-seed measurements may differ.

## Official practice run for 1b2da3d

All four tracks passed every gate; run IDs and measurements are in `board-1b2.json`. The checked Rust C candidate scored T=0.137394 s, M=17,235,968 bytes, S=170, K=17.662660. The preceding C++ practice run at 89795bb reported T=0.389804 s, M=80,576,512 bytes, S=213, K=7.446852. These are separate public-seed practice runs, not the final hidden-seed score. The original reported cold-cache SIGBUS remains unverified, as explained in `track-c/PERF.md`.

## Official practice run for 15c6be0

All four tracks passed the check, build, correctness, timeout and sandbox gates; measurements and run IDs are in `board-15c.json`. The nonlinear packed B candidate scored T=1.343342 s, M=256,245,760 bytes, S=379, K=8.038497. The preceding bounded candidate at 1b2da3d scored T=1.447820 s, M=256,856,064 bytes, S=335, K=7.883941. These are separate public-seed practice runs rather than paired or final hidden-seed scores.

## Official practice run for b9c2b54

All four tracks passed every gate; `board-b9.json` records the exact run IDs. A six-worker default measured T=0.050492 s versus the previous auto-worker T=0.047562 s. Because the priority is absolute speed, auto workers were restored for another target-machine comparison; the six-worker source is `a-six-b9/main.rs`. C 1024 shards measured 0.135942 s versus 0.136191 s for the prior 256 shards. D meeting-update measured 0.717778 s versus the prior 0.802058 s, with K 8.920170 versus 8.451791. These are separate public-seed practice runs; differences may reflect run-to-run variability. The full public board JSON response was truncated, but PeppaPig's complete team object was decoded and its commit and all gates verified.

## Official practice run for e8e828a

All four tracks passed every gate; see `board-e8.json`. A auto workers measured 0.051316 s, compared with 0.050492 s for six workers at b9c2b54 and 0.047562 s for auto at 15c6be0. These separate runs do not establish a reliable ordering, and the auto default is retained pending controlled target measurements. B/C/D measured 1.466380 / 0.139036 / 0.713930 s respectively. This is public-seed practice, not final hidden-seed scoring.

## Official practice run for e6e72ac

All four tracks passed every gate; `board-e6.json` records all run IDs and measurements. B length-aware hashing with nine workers measured T=1.124940 s, M=274,243,584 bytes, S=379, K=8.665777, versus the preceding 1.466380 s and K=7.698133. Separate public-seed practice runs are not paired or final hidden-seed scores.

## Official practice run for merged PR d144adc

All four tracks passed all gates; `board-d144.json` records run IDs. B's bounded Rust adaptation measured T=0.394683 s, M=225,353,728 bytes, S=343, K=15.445575, versus the previous B practice's T=1.124940 s, M=274,243,584 bytes, S=379, K=8.665777. A/C/D measured 0.050702/0.134472/0.701512 s respectively. These are separate public-seed practice runs rather than paired or final holdout scores.

## Official practice run for 073646e

All four tracks passed every gate; `board-073.json` records run IDs. D balanced-frontier measured T=0.383672 s, M=444,030,976 bytes, S=246, K=12.184975, versus the previous D run's T=0.701512 s, M=455,716,864 bytes, S=236, K=9.020576. A/B/C measured 0.051055/0.408505/0.146822 s respectively. These are separate public-seed practice runs, not final holdout scores.

## Official practice run for 4f2d688

All tracks passed every gate; see `board-4f.json`. C's CRLF synchronization measured T=0.137385 s, M=18,157,568 bytes, S=175, K=17.404341, versus 0.146822 s, 17,391,616 bytes, S=170 and K=17.055466 for the previous run. The runs are separate public-seed practice measurements, not final or controlled paired scores.

## Official practice run for 147d5b4

All tracks passed every gate; see `board-147.json`. B's eight-byte transition scanner measured T=0.381505 s, M=222,068,736 bytes, S=399, K=15.402876, versus 0.403564 s, 218,177,536 bytes, S=343 and K=15.373863 for the previous run. A/C/D measured 0.049667/0.128956/0.371431 s respectively. The runs are separate public-seed practice measurements, not final or controlled paired scores.

## Official practice run for b07315c

All tracks passed every gate; see `board-b073.json`. B's guarded AVX2 tokenizer measured T=0.341042 s, M=222,486,528 bytes, S=427, K=16.120054, versus the prior 0.381505 s, 222,068,736 bytes, S=399, K=15.402876. A/C/D measured 0.048257/0.127346/0.378481 s respectively. The separate public-seed practice runs are not final or controlled paired scores.

## Official practice run for 23ffdfc

All tracks passed every gate; see `board-23f.json`. B's exact short-token table measured T=0.346703 s, M=223,195,136 bytes, S=478, K=15.709610, compared with the previous run's T=0.341042 s, M=222,486,528 bytes, S=427, K=16.120054. Two prior dot VM paired passes favored the candidate by 7.8–9.3% wall; the official single-run difference is small and opposite, so a repeat on the scoring box is warranted before deciding. These are separate public-seed practices, not final holdout scores.

## Same-code official repeat for e88ee2c

The e88ee2c push changed experiment records and B performance notes, not selected source or Dockerfiles. All tracks passed every gate; see `board-e88.json`. B repeated at T=0.315290 s, M=224,714,752 bytes, S=478, K=16.451282. The same candidate's previous run was 0.346703 s, and the earlier AVX2 baseline run was 0.341042 s. Separate board runs are not paired and exhibit variation; the repeat and two dot VM paired batches support retaining the short-token candidate for speed. These are public-seed practices, not final hidden-seed scores.

## Official practice run for 8c273db

All tracks passed every gate; `board-8c.json` records run IDs. B's dense Boolean summary measured T=0.303369 s, M=223,789,056 bytes, S=496, K=16.692436, versus 0.315290 s, 224,714,752 bytes, S=478, K=16.451282 for the preceding practice. A/C/D measured 0.050286/0.129274/0.384428 s. Separate public-seed runs are not paired or final holdout scores.

## Official practice run for 5934716

All tracks passed every gate; `board-593.json` records run IDs. C bounded batching measured T=0.134421 s, M=29,593,600 bytes, S=208, K=15.549336, compared with the preceding practice at 0.129274 s, 17,870,848 bytes, S=175, K=17.999239. Two dot VM batches had favored batching by 13.5–18.2%, so the opposite small official wall difference needs another same-code scoring-box run. Separate public-seed practices are not paired or final holdout scores.
