# Track B Linux x86 sandbox profile (local diagnostics; not a candidate, not official scores)

`baseline.rs` is byte-identical to `track-b/src/main.rs` at `dddc0ea`, SHA-256 `6607a94ce52f9d1fd25e99f2e5705a9f79bc1f47b2c398bda148594124e63709`. `profile.rs` (SHA-256 `8ca7edd441cfcfb6b5f4fd8cc42e797ab789d55329892c3f75a1dec8b69b68d0`) adds `Instant` timestamps, `/proc/self/status` and optional `/proc/self/smaps_rollup` reads and an optional memory sampler thread around the existing phases, index chunks, answer blocks and query kinds, and an `ENDNS` stamp after its stderr dump. `profile-scan.rs` (SHA-256 `bfafd6714b605cb853e90aeb8f0b7037dc34e9f113c707bdb74f43a87c328bd7`, x86_64 only) is `profile.rs` without `ENDNS` plus `rdtsc` accumulators and token-class counts inside the chunk scan. `report.json`, `profile-threads-report.json` and `mem-report.json` were measured with the previous `profile.rs` (SHA-256 `def63048...`, commit `f321232`), which lacks only the `ENDNS` line and the reworded query-kind comment; `tail-report.json` was measured with the current one. `scan-report.json` was measured before the same comment-only change to `profile-scan.rs` (previous SHA-256 `f261f887...`). Neither changes output logic: every measured and warmup run of every binary, including the interleaved uninstrumented baseline runs, produced the published full seed-1 hash `f86973c210228141bcb6f1f1b10188ad2a9b65f71e7cd7cf4590b38de4e80927`, which `run.py` asserts. Production `track-b/` sources, `Cargo.toml` and `Dockerfile` are unchanged.

All numbers below are medians over measured runs, taken from the JSON reports in this folder. They are local sandbox measurements, not official scores.

## Environment

| Item | Value |
| --- | --- |
| CPU | Intel Xeon Platinum 8488C, 8 vCPUs (4 cores x 2 SMT), shared host |
| Kernel | 6.1.188-233.393.amzn2023.x86_64 |
| Compiler | rustc 1.92.0 (official Dockerfile pins Rust 1.99.1) |
| Flags | `-C target-cpu=x86-64-v3`, `lto=fat`, `codegen-units=1`, `panic=abort`, opt-level 3; AVX2 tokenizer path compiled |
| PGO | none locally (official build uses PGO trained on generator seed 2 sample) |
| Data | full seed 1, `docs.txt` 253,827,587 B, `queries.txt` 1,763,534 B, input hashes match `official/specs/b-index.md` |
| Output | fresh tmpfs `/tmp` directory per run |
| Tools absent | perf, valgrind, `/usr/bin/time`, cgroup `memory.peak`, working Docker |

Resource numbers come from `os.wait4` rusage of the child (`ru_maxrss` KiB, faults, context switches). Instrumented binaries also report `/proc/self/status` at phase boundaries.

## End-to-end, uninstrumented production binary

`baseline-report.json`: cargo release build of `track-b/` (binary SHA-256 `e9fdca31...`), default 8 threads, 1 warmup + 7 measured.

| Metric | Median |
| --- | ---: |
| Wall | 0.2270 s |
| User / sys CPU | 1.495 s / 0.057 s |
| CPU total | 1.539 s (6.82x wall) |
| Max RSS | 65,876 KiB |
| Minor / major faults | 25,344 / 0 |
| Voluntary / involuntary ctx switches | 141 / 315 |

Thread sweep of the same binary (`threads-report.json`, `SD_THREADS`, 1 warmup + 5 per setting):

| Threads | Wall s | CPU s | Wall speedup vs 1 | Max RSS KiB | Minor faults |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | 1.0366 | 1.036 | 1.00 | 58,572 | 20,323 |
| 2 | 0.5425 | 1.044 | 1.91 | 58,360 | 20,786 |
| 4 | 0.2910 | 1.069 | 3.56 | 61,512 | 22,364 |
| 6 | 0.2748 | 1.366 | 3.77 | 63,484 | 23,614 |
| 8 | 0.2233 | 1.529 | 4.64 | 65,852 | 25,385 |

Up to 4 threads total CPU is flat (about 1.04 to 1.07 s), so scaling is near-linear on the 4 physical cores. Beyond 4 threads CPU rises to 1.53 s for a 1.30x wall gain, consistent with SMT siblings sharing cores.

## Instrumentation overhead

| Report | Profiled wall / baseline wall | CPU ratio | Max RSS ratio |
| --- | ---: | ---: | ---: |
| `report.json` (profile.rs, 8t, 1+7) | 1.023 | 1.017 | 1.028 |
| `scan-report.json` (profile-scan.rs, 8t, 1+5) | 1.036 | 1.036 | 1.027 |
| `profile-threads-report.json` (1/2/4/6/8t, 1+5 each) | 0.990 to 1.027 | 0.979 to 1.014 | 1.021 to 1.049 |
| `tail-report.json` (profile.rs with `ENDNS`, 8t, 1+7) | 1.061 | 1.023 | 1.033 |

Baseline and profiled runs alternate within each report, so the ratios share host conditions. The wall ratios include the profiler's own reporting tail after the last phase (about 2.0 ms, below), roughly 0.9 points of each 8-thread ratio. The 1.061 of `tail-report.json` against 1.023 of `report.json` for nearly the same code is host noise between sessions. `mem-report.json` adds a 9th sampler thread and smaps reads (wall 0.2355 s) and is used only for memory.

## Phase breakdown (profile.rs, 8 threads)

`report.json`. Each phase ends at its `PHASE` timestamp; the following `/proc` read is charged to the next phase. Instrumented process wall 0.2300 s = main 224.54 ms + 5.54 ms after the `write` stamp. That after-write time is not all exec, loader and exit: it also contains the profiler's reporting work (QKIND/QSLOW/INFO lines over the 50,000-entry per-query vector and the stderr dump). `tail-report.json` splits it with the `ENDNS` stamp: after-write 5.79 ms = reporting tail 2.00 ms (1.94 to 2.10 ms over the 7 runs) + 3.75 ms really outside main. The committed `report.json` and `profile-threads-report.json` predate `ENDNS` and store the after-write value under the key `outside_main_ms`; `run.py` now names it `after_write_ms` and sets `outside_main_ms` only when `ENDNS` is present.

Two small attribution shifts come from the instrumentation itself: profile.rs flattens the per-thread results (and concatenates their logs) after the `index` and `answer` stamps, so that flatten is charged to `chunk_sort` and `outs_sort_concat` instead of the parallel phases; both phases stay small.

| Phase | ms | % of main | Kind |
| --- | ---: | ---: | --- |
| read_queries | 0.78 | 0.3 | serial |
| parse_intern | 15.35 | 6.8 | serial |
| mmap | 0.06 | 0.0 | serial |
| sample_scan | 2.51 | 1.1 | serial |
| plan_build | 3.84 | 1.7 | serial |
| rows_alloc | 0.04 | 0.0 | serial |
| index | 172.50 | 76.8 | parallel |
| chunk_sort | 0.07 | 0.0 | serial |
| hits_collect | 0.52 | 0.2 | serial |
| answer | 27.80 | 12.4 | parallel |
| outs_sort_concat | 1.55 | 0.7 | serial |
| write | 0.60 | 0.3 | serial |
| **main total** | **224.54** | 100 | serial 25.57 ms (11.1%), parallel 199.48 ms (88.9%) |

## Thread sensitivity and Amdahl

`profile-threads-report.json` (profile.rs, interleaved with baseline):

| Threads | Wall s | Index ms | Answer ms | Parallel ms | Serial ms | After write ms (incl. about 2.0 ms profiler tail) | Parallel speedup vs 1 | Chunks | Index idle tail ms |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | 1.0578 | 880.0 | 148.4 | 1027.4 | 25.0 | 5.4 | 1.00 | 16 | 0.0 |
| 2 | 0.5499 | 448.1 | 73.4 | 519.0 | 25.6 | 5.4 | 1.98 | 16 | 5.1 |
| 4 | 0.2999 | 232.1 | 36.6 | 269.3 | 25.2 | 5.6 | 3.82 | 16 | 3.8 |
| 6 | 0.2860 | 222.4 | 32.6 | 254.5 | 25.7 | 5.8 | 4.04 | 18 | 68.6 |
| 8 | 0.2288 | 170.4 | 28.2 | 198.2 | 25.2 | 5.7 | 5.18 | 16 | 6.4 |

Serial time is about 25 ms at every thread count (parse_intern about 15.3 to 15.8 ms of it), plus 5.4 to 5.8 ms after the write stamp, of which about 2.0 ms is profiler reporting (measured at 8 threads in `tail-report.json`; the reporting work does not depend on the thread count), leaving about 3.4 to 3.8 ms outside main. Summed scan time across threads grows from 823 ms (1t) to 1220 ms (8t), the SMT cost seen in the CPU column.

**6-thread anomaly (measured).** `nchunks = nthreads * ceil(len / (nthreads << 24))` gives 16 chunks for 1, 2, 4 and 8 threads but 18 chunks (3 per thread, 14.1 MB each) at 6 threads. At 6 threads index busy time ranged 156.6 to 221.0 ms per thread, utilization 0.893, idle tail 68.6 ms, so 6 threads were barely faster than 4. With 6 threads on 4 physical cores some threads share a core and others do not; the per-thread spread is consistent with that, but the cause is not isolated.

**12 threads (hypothesis to check).** With `len` 253,827,587 the formula gives `12 * ceil(253827587 / 201326592) = 12 * 2 = 24` chunks of about 10.6 MB, 2 per thread, so the 3-per-thread staircase of the 6-thread case does not recur by construction. Whether 2 chunks per thread leaves a tail on the scoring box (12 SMT threads on 6 P-cores) cannot be measured here; it needs a board run or an `SD_THREADS`-style experiment on 12-thread hardware.

**Amdahl extrapolation (hypothesis, this CPU's per-core speed).** Parallel work at 1 thread is 1027.4 ms; serial in main is about 25.2 ms. Outside main is about 3.7 ms: the 8-thread after-write value of `profile-threads-report.json` (5.68 ms) minus the 2.00 ms reporting tail measured in `tail-report.json` (derived across two reports, not measured in one run; `tail-report.json` alone gives 3.75 ms). The serial term is therefore 25.2 + 3.7 = 28.9 ms.

- Perfect 12-way scaling: 1027.4 / 12 + 28.9 = 114 ms; serial plus outside would then be 25% of wall.
- SMT-aware: measured parallel speedup is 3.82 at 4 threads (one per core) and 5.18 at 8 threads (SMT), i.e. about 1.30 effective cores per physical core with SMT. Applying that to 6 cores x 2 SMT gives about 7.8 effective cores: 1027.4 / 7.8 + 28.9 = 161 ms, with the 28.9 ms serial part about 18% of wall.

The i5-13500 P-core speed, memory bandwidth, SMT yield and Rust 1.99.1 PGO code all differ, and recent official B practices measured T 0.29 to 0.31 s (older source; current HEAD has no board run), well above both the local 8-thread wall and this projection. The extrapolation only says the serial share grows as threads increase; it does not predict T.

## Index load balance (8 threads)

`report.json`, 16 chunks, 2 per thread:

| Metric | Value |
| --- | ---: |
| Index window | 172.50 ms |
| Busy per thread min / mean / max (median over runs of each run's min / mean / max) | 163.86 / 166.84 / 171.09 ms |
| Utilization | 0.980 |
| Spawn delay / idle tail / join delay | 0.20 / 6.80 / 0.06 ms |
| Busy sum (scan + CSR) | 1334.7 ms (scan 1227.5, CSR 109.6; CSR 8.2% of busy) |
| Chunk scan median / max | 76.05 / 82.50 ms |
| Chunk CSR median / max | 7.09 / 8.77 ms |
| Scan throughput per thread | 206.8 MB/s |

Taking instead each thread's median busy time over the runs, the 8 threads range 165.3 to 168.1 ms (`index_by_thread`); the narrower range is because a run's fastest and slowest thread vary between runs. Balance at 8 threads is good, and the remaining tail (6.8 ms, about 4% of the index window) is roughly one tenth of a chunk.

## In-scan split (profile-scan.rs, 8 threads)

`scan-report.json`, TSC 2.40 cycles/ns, 36,276,657 tokens per run (145.1 per document), 250,000 documents. Percentages are of the summed parts (1321.2 ms); 2.7% of the measured total is unattributed. The unattributed share includes the profiler's own token-class counting loop (list/bitmap/none/other counts over all tokens, run inside the chunk total but outside every timed part), the final flush, the stream allocation and the timer calls, so it is not all production work.

| Part | What it covers | % | cycles/token | ns/token | ms summed over threads |
| --- | --- | ---: | ---: | ---: | ---: |
| masks | AVX2 tab/delimiter masks, bounds, key build, prefetch, push | 30.8 | 27.1 | 11.3 | 410.4 |
| lookup | slot lookup + token extend | 34.9 | 30.6 | 12.7 | 462.1 |
| callback | group bitmap flush, u16 stream push (minus phrase) | 20.3 | 17.8 | 7.4 | 269.8 |
| phrase | anchor prefetch + phrase compare | 4.2 | 3.7 | 1.5 | 55.7 |
| release | clear + `madvise` every 1 MiB | 1.0 | 0.9 | 0.4 | 13.1 |
| csr | counting sort CSR + dedup + compaction | 8.5 | 7.4 | 3.1 | 111.7 |

Token classes per run: bitmap terms 16,190,014 (44.6%), list terms 11,371,204 (31.3%), no query term 7,559,960 (20.8%), phrase-only 1,155,479 (3.2%), long 3,969. Anchors checked 1,674,857, phrase hits 19,427. `n_list` equals `chunk_docs_entries` (11,371,204), so in seed 1 no list term repeats within a document and the CSR dedup never removes an entry.

## Answer phase (profile.rs, 8 threads)

`report.json`: 782 blocks of 64 queries, window 27.80 ms, utilization 0.985, idle tail 0.20 ms, block median 274 us, max 645 us. Boolean queries take 210.8 ms of the 214.8 ms summed query time (98.1%); 19,000 phrase queries take 4.05 ms in total because their hits were collected during the scan.

| Kind | Count | Total ms | Mean us | Max us | Mean clauses |
| --- | ---: | ---: | ---: | ---: | ---: |
| bool_list (no bitmap term, bitmap never used) | 20,690 | 87.28 | 4.22 | 197.8 | 2.75 |
| bool_list_bm (no bitmap term, bitmap used after a large OR spill) | 3,730 | 60.86 | 16.32 | 142.3 | 3.30 |
| bool_row_bm (bitmap term, bitmap used at some point) | 4,026 | 51.48 | 12.79 | 208.3 | 3.30 |
| bool_row_list (bitmap term, bitmap never materialized) | 2,554 | 12.90 | 5.05 | 117.2 | 3.37 |
| phrase | 19,000 | 4.05 | 0.21 | 39.2 | 3.25 |

"Bitmap used" means the running result was the bitmap at some point in the query. A later AND with a list term turns it back into a list, so a `*_bm` query may still finish on the list path; the kinds do not say which representation produced the final result.

The queries most often in a run's slowest 20 are bitmap-heavy Boolean queries (for example query 43677, `bool_row_bm`, 6 clauses, in the top 20 in 6 of 7 runs, median 84 us). Single-run outliers up to 6.2 ms appear only once each and look like preemption on the shared host, not query cost.

## Memory

Per-phase `/proc/self/status` (`report.json`, kB):

| After phase | VmHWM | VmRSS | RssAnon | RssFile |
| --- | ---: | ---: | ---: | ---: |
| read_queries | 3,804 | 3,804 | 1,756 | 2,044 |
| parse_intern | 10,876 | 10,876 | 8,764 | 2,108 |
| sample_scan | 11,596 | 11,596 | 9,420 | 2,172 |
| plan_build / rows_alloc | 15,024 | 15,024 | 12,848 | 2,172 |
| index | 64,624 | 64,068 | 60,772 | 3,288 |
| answer | 64,780 | 64,616 | 61,292 | 3,288 |
| outs_sort_concat | 67,684 | 67,684 | 64,364 | 3,296 |
| write / exit | 67,684 | 66,376 | 63,028 | 3,296 |

The peak (VmHWM 67,684 kB, equal to rusage max RSS) is reached in outs_sort_concat, when the per-block output strings and the 1.46 MB concatenated result are both live. Part of that peak is profiler state: in the same window profile.rs merges the per-query timing vectors (50,000 entries of 16 bytes, about 0.8 MB) and concatenates the per-thread BLOCK logs, and the IDX log is still held. The interleaved uninstrumented baseline in `report.json` peaked at 65,872 KiB, 1,812 KiB lower (`tail-report.json`: 65,484 vs 67,644 KiB). So roughly 1.8 MB of the instrumented peak is likely instrumentation (inferred from allocation sizes and the max RSS difference, not traced at allocator level), and the production outs plus concat window is smaller than the instrumented table suggests. The 1 ms sampler (`mem-report.json`, 204 samples) saw max RssAnon 64,448 kB and max RssFile 5,464 kB during indexing, so the per-1 MiB `madvise` keeps mapped file pages around 2 to 5 MB. `smaps_rollup` Anonymous: 13,220 kB after rows_alloc, 61,160 kB after index, 61,684 kB after answer, 64,000 kB at write.

Structure sizes reported by `INFO` (bytes per run):

| Structure | Bytes | Notes |
| --- | ---: | --- |
| chunk postings docs | 22,742,408 | 11,371,204 u16 entries |
| bitmap rows | 10,845,832 | 347 bitmap terms x 3,907 words x 8, first-touched by scanners |
| stream buffers (live) | about 15.9 M | 1,988,216 B max capacity per chunk x 8 threads; 31.7 MB summed over all 16 chunks |
| chunk postings offsets | 3,398,272 | 16 chunks x 53,098 x 4; scales with nchunks |
| plan keys | 3,145,728 | 131,072 slots |
| query vectors | 3,044,784 | |
| sample freq/last | 908,976 | |
| aoff + anchors + flat + role | 929,688 | |
| hoff | 400,008 | |
| chunk hits + hits | 419,968 | 19,427 hits |
| outs / results.txt | 1,459,301 | results.txt also lands on tmpfs |

The table also lists `hits` (157,824 B) and `hoff` (400,008 B), which are allocated only after the index phase. Known structures live after index, excluding streams, sum to 45.3 MB (44,216 KiB); adding one stream buffer of maximum capacity per thread gives 59,749 KiB, about 1 MB below the 60,772 kB RssAnon after index. That rough match suggests (hypothesis) that freed stream buffers stay resident in malloc arenas; the code was not instrumented at allocator level.

At 12 threads the formula gives 24 chunks, so offsets grow to about 5.1 MB, and 12 live stream buffers would be about 23.9 MB (arithmetic from the measured per-chunk sizes; the 10.6 MB chunks would likely need smaller streams).

## Ranked bottlenecks and implied levers

Measured shares are from the tables above. Levers are hypotheses until a candidate is measured; under `K = (Tref/T)^0.5 x min(50, Mref/M)^0.2 x min(1, Sref/S)^0.15 x D`, with the S penalty active, a lever that grows source by x% needs roughly a 0.3x% T reduction just to break even (0.15 / 0.5). For example `track-b/src/main.rs` at `dddc0ea` has 619 nonempty non-comment lines after local rustfmt 1.8.0 (not the official scc count, which also includes the Dockerfile and has no board run at this commit), so 60 more lines (+9.7%) need about 3% lower T.

1. **Index scan tokenize + lookup (measured: index is 76.8% of main; masks + lookup are 65.7% of scan parts, about 58 cycles/token).** Lookup alone is 34.9% (30.6 cycles/token) and 20.8% of tokens are not query terms at all. Levers: a cheaper negative filter before the full slot probe for the 7.56M non-query tokens (for example a length/first-bytes bitset or a compact fingerprint array), a smaller or more cache-friendly key table (plan keys are 3.15 MB); reduce work in the mask/key step per token. Hypothesis: lookup cost is dominated by cache misses on the 131,072-slot table; no hardware counters were available to confirm.
2. **Answer phase Boolean evaluation (measured: 27.8 ms, 12.4% of main; BOOL 98.1% of it).** `bool_list` dominates by count (87 ms summed) and `bool_list_bm` (running result spilled to the bitmap by a large OR at some point) is the most expensive per query (16.3 us, 61 ms summed for 3,730 queries). Levers: faster list intersection/union for 2 to 3 clause list queries; revisit the threshold or method that converts large ORs to bitmaps; phrase answering is already negligible.
3. **Serial parse_intern (measured: 15.35 ms, 6.8% of main at 8t, constant across thread counts).** It is 60% of all serial time and its share grows with threads (Amdahl section). Levers: parallel query parsing/interning, or overlapping it with the start of the scan. Hypothesis: on 12 threads this is worth relatively more than locally.
4. **Chunk sizing and SMT (measured: 6.8 ms tail at 8t; 68.6 ms tail at 6t from 18 chunks; SMT gives about 1.30x per core).** Levers: decouple chunk count from thread count (more, smaller chunks claimed dynamically) to bound the tail by a smaller granule, at the cost of about 212 KB of offsets per extra chunk plus per-chunk CSR overhead. Hypothesis: the 12-thread case (24 chunks) behaves like 8t here; check on 12-thread hardware.
5. **Memory (measured: peak RSS 67.7 MB; chunk docs 22.7 MB, live streams about 16 MB, bitmap rows 10.8 MB).** Levers: free or shrink stream buffers sooner (or reuse one per thread), trim allocator retention, avoid holding outs and the concatenated string together (in production that window is smaller than measured here: about 1.8 MB of the instrumented peak is profiler state, see Memory; uninstrumented max RSS is about 65.9 MB). Hypothesis: official M (about 224 MB) is much larger than local RSS, so it includes components not seen here (for example page cache or harness accounting); anonymous memory savings may move M only modestly, and M has the smaller exponent (0.2). Check against a board run before spending S on memory.

## Caveats

- The sandbox is a shared Xeon Platinum 8488C with 8 vCPUs (4 cores x 2 SMT), not the scoring i5-13500 (6 P-cores / 12 threads, AVX2, no AVX-512). Thread counts, SMT yield and per-core speed differ; nothing here was run with 12 threads.
- rustc 1.92.0 without PGO locally versus Rust 1.99.1 with PGO officially; code layout and inlining differ.
- Official M is a cgroup memory peak including tmpfs writes; locally only rusage max RSS and `/proc` were available.
- Timings include host noise; each report uses 1 warmup and 5 or 7 measured runs, medians only. Instrumentation adds 1 to 6% wall (about 2 ms of it is the reporting tail after the last phase) and extra stderr writes.
- Phase durations use phase-end timestamps; `/proc` reads fall into the following phase.
- Seed 1 only. The finding that list terms never repeat within a document is a property of this dataset.

## Reproduce

```sh
# data (outside the repo; ~90 s)
python3 official/generators/b_index.py --seed 1 --scale full --out /projects/sandbox/.data/speed-b-full

# builds
(cd track-b && RUSTFLAGS='-Ctarget-cpu=x86-64-v3' cargo build --release)
mkdir -p /projects/sandbox/.data/bin
for s in baseline profile profile-scan; do
  rustc --edition=2021 -O -C lto=fat -C codegen-units=1 -C panic=abort -C target-cpu=x86-64-v3 \
    experiments/b-linux-profile/$s.rs -o /projects/sandbox/.data/bin/$s
done

D=/projects/sandbox/.data/speed-b-full; B=/projects/sandbox/.data/bin; R=experiments/b-linux-profile
python3 $R/run.py --binary track-b/target/release/solution --data $D --runs 7 --report $R/baseline-report.json
python3 $R/run.py --binary track-b/target/release/solution --data $D --threads 1,2,4,6,8 --runs 5 --report $R/threads-report.json
python3 $R/run.py --binary $B/profile --baseline $B/baseline --data $D --runs 7 --report $R/report.json
python3 $R/run.py --binary $B/profile-scan --baseline $B/baseline --data $D --runs 5 --report $R/scan-report.json
python3 $R/run.py --binary $B/profile --baseline $B/baseline --data $D --threads 1,2,4,6,8 --runs 5 --report $R/profile-threads-report.json
python3 $R/run.py --binary $B/profile --data $D --runs 5 --env SD_PROF_SMAPS=1 --env SD_PROF_SAMPLE_US=1000 --report $R/mem-report.json
python3 $R/run.py --binary $B/profile --baseline $B/baseline --data $D --runs 7 --report $R/tail-report.json
```

`run.py` uses one warmup by default, a fresh tmpfs output directory per run, and fails on any output hash mismatch (an explicit check, so it also runs under `python3 -O`). Rebuilding profile.rs now adds `ENDNS` lines to the reports made before it existed; otherwise the instrumentation is unchanged. Do not run other workloads during timing. No data, binaries or credentials are committed.
