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

A's three-shard buffered version was selected locally after the native x86 comparison and GCC warning review; the prior selected source is `a-serial-f45.cpp`, and the warning-free resize-and-copy alternative is `a-three-shard-checked.cpp`. C mmap and D parallel parsing remain experiments: using pinned formatter/scc counts and VM process measurements, their modeled K ratios were about 1.029 and 1.003, respectively, before official cgroup measurements. Details are in `dot-vm.md`; pinned static-count evidence is in `static-f45/`, C mmap source, edge fixtures and measurements are in `c-mmap*`, and the D experiment and tests are in `track-d-parallel-parse/`.

A later Track B rare-anchor phrase experiment was about 2.1% slower than its zero-copy baseline on local full data. Local worker-count tests favored six workers over three and twelve; a 4 MiB read buffer's estimated 1.3% time/memory gain was too noisy to justify the extra memory. The failed/marginal experiments, commands, and data are in `b-iteration-summary.md` and matching sources and JSON files. The selected B remains unchanged.
