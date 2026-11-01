# Track B candidate: lower peak memory (local sandbox measurements, not official scores)

`baseline.rs` is byte-identical to `track-b/src/main.rs` at `b7c4ae5` (and to `experiments/b-speed3/candidate.rs` on branch `b-speed3`), SHA-256 `d39202542d59ccededa7fd0b7bbbd3c703d63f5dd98a80e02dd97f2acaff66b9`. `candidate.rs` is byte-identical to the committed `track-b/src/main.rs` of this candidate, SHA-256 `c18e6044047c93b834e55e14b9e6a16b59643e7b64a678480736d9d71dde048b`. `Cargo.toml`, `Cargo.lock` and `Dockerfile` are unchanged. std only; the one new libc function, `mallopt`, is declared in the existing `extern "C"` block next to `mmap` and `madvise`.

All numbers below are local sandbox measurements, not official scores and not board results. The only official numbers quoted are those of the baseline: board run `run-2802b79df46d` measured `b7c4ae5` at T=0.172 s, M=73.8 MB, S=583, K=27.00. No board run exists yet for this candidate.

## Summary

| | baseline (`b7c4ae5`) | candidate |
| --- | ---: | ---: |
| S (`rustfmt --edition 2021 --emit stdout <file> \| grep -cvE '^\s*$\|^\s*//'`) | 558 | 565 (+7, +1.25%) |
| Raw lines | 672 | 687 |
| Max RSS, median of 21 runs (ratio of medians), 12 threads | 67,956 KiB | **49,244 KiB (-27.5%)** |
| Max RSS, median of 21 runs, 8 threads | 62,632 KiB | **49,444 KiB (-21.1%)** |
| Max RSS, median of 21 runs, 6 threads | 61,972 KiB | 50,388 KiB (-18.7%) |
| Max RSS with all chunk CSRs of a round aligned (worst case, below), 12 / 8 threads | 68,056 / 62,728 KiB | 50,652 / 51,388 KiB (-25.6% / -18.1%) |
| Paired wall, 21 pairs, 12 / 8 / 6 threads | | -1.93% (16/21) / -1.24% (14/21) / -8.69% (19/21) |
| Paired CPU, 12 / 8 / 6 threads | | -2.29% / -1.30% / +0.48% |
| Estimated K factor (local estimate, below) | | about 1.06, range 1.04 to 1.07 (K about 28.7 from 27.00) |

Max RSS is the child's `ru_maxrss` (KiB), which includes about 3.2 MiB of file-backed pages (the binary, libc and the mapped `docs.txt` pages not yet released). The board's M is a cgroup memory peak and also counts the 1.46 MB `results.txt` on tmpfs.

## Environment

| Item | Value |
| --- | --- |
| CPU | Intel Xeon Platinum 8488C, 8 vCPUs (4 cores x 2 SMT), shared host |
| Kernel, libc | 6.1.188-233.393.amzn2023.x86_64, glibc 2.34 (the official image is Debian 13, glibc 2.41; the malloc behaviour used here is the same) |
| Compiler | rustc 1.92.0, rustfmt 1.8.0 (the official Dockerfile pins Rust 1.99.1 and uses PGO) |
| Flags | `RUSTFLAGS='-Ctarget-cpu=x86-64-v3' cargo build --release` with the repo profile (fat LTO, 1 codegen unit, panic=abort) |
| Data | full seed 1 (`docs.txt` 253,827,587 B, `queries.txt` 1,763,534 B) |
| Timing harness | `experiments/b-linux-profile/run.py` (candidate and baseline interleaved, 1 warmup, hash asserted on every run), `experiments/b-filter-parse/pair.py` |
| Baseline binary | `/projects/sandbox/.data/bin/base-b7c4`, rebuilt from `b7c4ae5`, SHA-256 `aef038ddf1ab...`, byte-identical to `bin/s3-final` of b-speed3 |
| Candidate binary | SHA-256 `6d1ee070376ae735072fa96c9632aaa958415a3380123b20d737ebf9eedca63a` (the measured binary; a last comment-only edit of `candidate.rs` builds to the same bytes) |

The scoring box is an i5-13500 with 6 P-cores / 12 threads, where the code runs 12 threads and cuts 24 chunks. This host has 8 vCPUs, so 12 threads are oversubscribed here and do not run in step. On this host |wall delta| below about 1% is noise.

## Attribution of the baseline peak

`profile-baseline.rs` and `profile.rs` are `baseline.rs` and `candidate.rs` with memory instrumentation added by `tools/mkmem.py`: `/proc/self/status` (VmHWM, VmRSS, RssAnon, RssFile) and glibc `mallinfo2()` at every phase boundary, per-chunk stream and list sizes and times, an optional 100 us `/proc/self/statm` sampler (`SD_PROF_SAMPLE_US`), an optional `malloc_trim(0)` probe after a named phase (`SD_PROF_TRIM`), and `malloc_stats()` at exit. The instrumented binaries produce the seed-1 hash, and their median max RSS is within 1.5% of the uninstrumented binaries' (for example 49,436 vs 49,444 KiB for the candidate at 8 threads).

### When the peak happens

Baseline, medians of 5 sampled runs (`reports/mem/prof-sampled-t8.json`, `prof-sampled-t12.json`): the sampled anonymous peak is at 181 ms (8 threads) and 201 ms (12 threads), right after the answer phase ends (180 and 200 ms), when the per-block output strings and the concatenated `results.txt` string are both live. Through the index phase the anonymous RSS rises steadily, from 10,432 KiB before it to 57,696 KiB (8 threads) and 62,276 KiB (12 threads) at its end, and stays there during the answers.

### What is live at the peak

`reports/mem/prof-base-trimpeak-t8.json` and `-t12.json` (5 runs, medians) call `malloc_trim(0)` right after the output concatenation, at the peak:

| At the baseline peak (after `outs_sort_concat`) | 8 threads | 12 threads |
| --- | ---: | ---: |
| VmHWM | 62,660 KiB | 67,348 KiB |
| RssAnon / RssFile | 59,344 / 3,336 KiB | 64,032 / 3,224 KiB |
| RssAnon after `malloc_trim(0)` | 48,680 KiB | 50,236 KiB |
| **Freed memory still resident in malloc arenas** | **10,664 KiB** | **13,796 KiB** |
| `mallinfo2`: arena total / in use / free | 30,924 / 16,335 / 14,587 KiB | 45,368 / 27,717 / 17,650 KiB |
| `mallinfo2`: mmapped blocks | 34,000 KiB in 22 | 24,264 KiB in 15 |

The live structures (sizes from the `INFO` lines; KiB):

| Structure | 8 threads | 12 threads | Needed after the scan |
| --- | ---: | ---: | --- |
| chunk lists `docs` (11,371,204 u16) | 22,209 | 22,209 | yes |
| bitmap rows (347 terms x 3,907 words) | 10,592 | 10,592 | yes |
| chunk `offs` (53,098 u32 per chunk; 16 or 24 chunks) | 3,319 | 4,978 | yes |
| `qs` (16 B per query) + `terms` (8 B per term) | about 2,000 | about 2,000 | yes |
| plan `keys` (131,072 slots), `filter`, `aoff`, `anchors`, `flat` | about 4,000 | about 4,000 | no |
| `qtext` and the sample-scan temporaries (`freq`, `bools`, `order`, `new`, the renumbered `freq`) | about 3,900 | about 3,900 | no |
| per-block outputs (1,425 used, 1,844 capacity) and the concatenated string (1,425 used, 2,048 capacity) | about 2,900 | about 2,900 | only to write |
| freed but resident in arenas (trim probe) | 10,664 | 13,796 | no |

The entries of this table sum to RssAnon within about 0.5 MiB at both thread counts (thread stacks and small buffers are not listed, and some outputs sit in reused arena memory). Of the 58.0 MiB (8 threads) and 62.5 MiB (12 threads) of anonymous memory, about 38.6 MiB (8 threads) or 40.2 MiB (12 threads) is needed at the end: lists, rows, offsets, queries and one copy of the output.

### Why freed memory stays resident

glibc serves blocks of at least `M_MMAP_THRESHOLD` (128 KiB at start) with their own mapping, but freeing such a block that is larger than the current threshold raises the threshold to that block's size (up to 32 MiB) and the trim threshold to twice that. In the baseline the first chunk to finish frees its stream buffer (1.3 MiB at 12 threads, 1.9 MiB at 8), so every later stream, `docs`, `offs` and `end` array below that size comes from the thread's arena, and freed streams and `end` arrays stay there, resident, until exit. The answer threads reuse some of it for their outputs (the answer phase adds only 180 to 340 KiB of RSS in the baseline), the rest is the 10.7 to 13.8 MiB above. At 12 threads more chunks and more arenas retain more, and `offs` is 1.6 MiB larger.

### What bounds the peak once nothing is retained

Removing the retention alone (step 1 below, a fixed mmap threshold) lowers the end-of-run level, but the peak then moves into the index phase: all threads build their chunk lists at about the same time, and while a thread runs its counting sort it holds both its stream buffer (0.0914 bytes per corpus byte) and its new `docs` array (0.0894 bytes per corpus byte). With two equal chunks per thread the second round of these overlaps with the finished first-round lists and all of the rows.

On this host 12 threads do not run in step, which hides that overlap. The instrumented builds therefore have `SD_PROF_LOCKSTEP=1`: a thread that has scanned its r-th chunk waits until every thread has, so all counting sorts of a round start together, as on a box where the threads scan at the same speed. It is a worst case for the overlap (the board takes the largest of five runs). With it, step 1 alone gives 61,812 vs 68,132 KiB at 12 threads and 62,080 vs 62,680 KiB at 8 threads (`reports/chain-hwm.txt`), much less than the free-running 12-thread figure (57,384 KiB) suggests. `tools/sim.py` is a lockstep model of the same effect (a model only, used to pick which schedules to measure).

## Changes kept

1. **Fixed mmap threshold.** `mallopt(M_MMAP_THRESHOLD = -3, 128 KiB)` at the start of `main` keeps glibc from raising the threshold, so every block of at least 128 KiB (streams, `docs`, `offs`, `qtext`, the plan tables) has its own mapping and is unmapped when freed. +2 S lines.
2. **Rounds of shrinking chunks.** The chunk count is unchanged (`nthreads * m`, m = 2 at 8 and 12 threads), but round r of `nthreads` equal chunks now covers 4(m - r) - 1 of m(2m + 1) parts of the bytes: 70% then 30% for m = 2 (11:7:3 for m = 3, equal chunks for m = 1). The second round's streams are small and fewer bytes of lists exist during the first round's sorts, which balances the two overlap peaks. First-round chunks are 1.4 times the old equal chunks at 8 and 12 threads (22.2 MB, about 22,000 documents, at 8 threads) and at most 1.9 times at 1 thread (30.3 MB); the existing assert still checks the 65,536-document limit of the u16 ids. +2 S lines.
3. **Early drops.** `qtext` and the sample-scan temporaries are dropped once the anchors are chosen, before the rows are allocated (the second `freq` is renamed `df` so that one `drop` covers both). +1 S line.
4. **Counting sort without the `end` copy.** `offs` has nl + 2 slots: `offs[l + 2]` counts list l, after the prefix sum `offs[l + 1]` is where list l's next id goes, and after the fill `offs[l]` is the start of list l. The fill no longer checks for repeats; a second pass drops a term's repeats within a document, which are equal neighbours in its sorted list, and closes the gaps. No 212 KB clone of `offs` per chunk, and the counting sort is faster: summed over the chunks of an 8-thread run, 105.6 ms vs 118.4 ms for the candidate with the old counting sort (`reports/csr-cost.txt`). +1 S line.
5. **Drop the scan-only tables after the index.** `plan.keys`, `filter`, `aoff`, `anchors` and `flat` (about 4 MiB) are replaced by empty vectors once the scan is done; otherwise the end of the run becomes the peak at 12 threads. +1 S line.
6. **u32 query offsets.** `qs` holds `(u8, u32)` instead of `(u8, usize)`, 400 KB less. 0 S lines.

Steps as measured (each patch in `steps/` applies to the previous file; applied in order to `baseline.rs` they give `candidate.rs`): 1 = change 1; 2 = change 2 with a 3:1 split plus change 3 (with a block instead of a rename); 3 = changes 4 and 5; 4 = the 7:3 split and change 6; 5 = the same code in fewer lines; 6 = comments only.

### Memory along the steps

Instrumented builds, 5 runs each, median VmHWM in KiB (`reports/chain-hwm.txt`):

| Step | 8 threads lockstep | 8 threads free | 12 threads lockstep | 12 threads free |
| --- | ---: | ---: | ---: | ---: |
| baseline | 62,680 | 62,756 | 68,132 | 67,300 |
| 1 fixed mmap threshold | 62,080 | 57,520 | 61,812 | 57,384 |
| 2 + rounds 3:1, early drops | 55,484 | 55,452 | 53,956 | 53,336 |
| 3 + CSR without `end`, late drops | 53,376 | 53,260 | 51,036 | 50,476 |
| 4 + rounds 7:3, u32 query offsets | 51,360 | 49,124 | 50,644 | 49,444 |
| candidate (same code as 4, fewer lines) | 51,396 | 49,572 | 51,364 | 49,328 |

### Leave-one-out

Each change removed from the candidate on its own (`variants/loo-*.patch`). Memory: instrumented, lockstep, 5 runs each, median VmHWM (`reports/loo-lockstep.txt`, measured with an earlier revision of `mkmem.py` that used other names for two output tags). Time: paired against the candidate code, 11 pairs (`reports/loo-*.json`; the reference binary there is step 5, the same code as the candidate) and 21 pairs for the two changes that could cost time (`reports/loo21-*.json`). A positive wall delta means the change makes the candidate faster.

| Removed | VmHWM lockstep 8 / 12 threads (KiB) | vs candidate | Wall when removed, 8 threads | 12 threads | S saved |
| --- | ---: | ---: | ---: | ---: | ---: |
| none (candidate code) | 51,364 / 50,684 | | | | |
| 1 fixed mmap threshold | 53,268 / 55,452 | +1,904 / +4,768 | -0.42% (21 pairs), -0.96% (11) | -0.32% (21), +0.15% (11) | 2 |
| 2 rounds (equal chunks) | 57,800 / 55,372 | +6,436 / +4,688 | -1.28% (21), -0.95% (11) | +2.02% (21), +2.86% (11) | 2 |
| 3 early drops | 55,276 / 55,360 | +3,912 / +4,676 | +0.04% (11) | +0.64% (11) | 1 |
| 4 old counting sort with `end` | 53,404 / 53,996 | +2,040 / +3,312 | +3.94% (11; faster in 1 of 11) | +2.78% (11; faster in 0 of 11) | 1 |
| 5 late drops | 51,364 / 53,160 | 0 / +2,476 | -1.16% (11) | -0.11% (11) | 1 |
| 6 u32 query offsets | 51,696 / 51,228 | +332 / +544 | +0.53% (11) | -0.90% (11) | 0 |

Every change lowers the 12-thread worst case. Two of them cost some time on this host:

- The fixed mmap threshold costs about 0.3 to 0.4% wall here (21 pairs, near noise; more fresh pages and `munmap` calls) for 4,768 KiB at 12 threads. Under the K formula (M with the board offset described under K estimate) that is about +1.7% for memory against -0.2% for time.
- The rounds cost about 1.3% wall at 8 threads. Part of it is the counting sort of the larger first-round chunks, which is slower per stream entry (9.17 vs 8.91 ns, `reports/csr-cost.txt`), probably because their 2 MB `docs` arrays exceed the 2 MB L2 that two SMT threads share here (no hardware counters to confirm). At 12 threads here they save 2% (the small last round shortens the tail when threads are oversubscribed) and at 6 threads the candidate is 8.7% faster than the baseline, mostly from them: 6 threads make 18 chunks, whose equal split left a long tail. The memory gain at 12 threads is 4,688 KiB, about +1.7% K against at most -0.65% K for 1.3% time. Kept.

### Split ratio

Rounds of `a:b` for m = 2 on step 3 (`variants/split-*-on-step3.patch`, a test form valid only for m = 2), instrumented, lockstep, 5 runs, median VmHWM (`reports/split-lockstep.txt`):

| First round share | 8 threads | 12 threads |
| --- | ---: | ---: |
| 2:1 (0.667) | 53,760 | 53,540 |
| 7:3 (0.700) | **51,732** | 51,492 |
| 5:2 (0.714) | 52,244 | 51,144 |
| 3:1 (0.750) | 53,392 | 51,012 |
| 4:1 (0.800) | 57,276 | 51,520 |

At 8 threads, where the threads do run in step on this host, 7:3 is clearly best; the first round's overlap dominates above it and the second round's below it. The 12-thread differences between 7:3, 5:2 and 3:1 are within the spread. With 24 chunks the second round holds 1.6 MiB more offsets than at 8 threads, which moves the 12-thread optimum up by about 0.01 (model), so 7:3 is kept. The general form 4(m - r) - 1 gives 7:3 for m = 2.

## Tried and rejected

| Variant | Result | Decision |
| --- | --- | --- |
| Fixed mmap threshold alone (step 1) | lockstep 62,080 / 61,812 KiB (8 / 12 threads) vs 62,680 / 68,132; free-running 12 threads 57,172 vs 67,204 (`reports/screen-step1-t12.json`) | kept as part of the candidate, but alone it mostly moves the peak into the index phase |
| `malloc_trim(0)` once after the index instead of the fixed threshold (`variants/trim-after-index-instead-of-mallopt.patch`) | lockstep 53,300 / 55,428 KiB vs candidate 51,384 / 50,992 (`reports/x-lockstep.txt`) | rejected: the retained second-round streams peak at the end of the index, before the trim runs, and which blocks are retained depends on the order of frees |
| Write the per-block outputs with `write_vectored` instead of concatenating them (`variants/writev.patch`) | lockstep 51,376 / 50,940 vs 51,384 / 50,992 KiB | rejected: no change, the end of the run is 3 to 6 MiB below the index peak once the scan tables are dropped; +5 S lines |
| Rounds 2:1, 5:2, 3:1, 4:1 | table above | 7:3 kept |

Considered and not built, with the reason:

- One stream buffer per thread, reused across chunks: with shrinking rounds it would keep the first round's touched pages (about 1.9 MiB per thread at 8 threads) resident during the second round, where the peak needs the streams smallest.
- Sizing the stream more tightly: with every large block mapped on its own, capacity that is never written is never resident, so only the 0.0914 bytes per corpus byte actually written count.
- Releasing the stream progressively during the fill (`madvise` on the consumed part): the `docs` regions are ordered by term, and almost every 4 KiB page of `docs` holds the list of some term that occurs in the first few documents, so `docs` becomes resident early in the fill and the overlap would barely change (reasoning from the layout, not measured).
- Building the CSR in the stream's own buffer: an entry would need both its term and its document to be moved in place, 4 bytes instead of 2.
- The bitmap threshold trade (lists for 1/32 < df/N < 1/16): at the first round's peak a list term costs its stream and `docs` entries for 70% of the corpus, 2.8 df bytes, against the 70% of its row already touched, 0.7 N/8 bytes, which is break-even exactly at the current 1/32 threshold. At the second round's peak the break-even is about N/21, so a 1/32 to 1/21 band of lists would save a little there and add to the first round's peak. At the end of the run, where lists are smaller than rows, memory no longer peaks.
- Two-level u16 offsets (u32 base per 64 lists): would save about 1.2 MiB at the second round's peak (the finished first-round offsets) for about 10 S lines, extra loads per list access in the answers, and an overflow fallback.
- A smaller `SLICE` for `docs.txt`: those are file pages of the pre-warmed page cache, not heap.

## Peak of the candidate

Medians of 5 sampled runs (`reports/mem/prof-sampled-*.json`): with lockstep the peak is at the first round's counting sorts at 8 threads (107 ms of a 154 ms index) and at the second round's at 12 threads (157 ms of 161 ms); free-running it is one or the other. What is live at the 8-thread lockstep peak, from the per-chunk lines of `reports/mem/prof-lockstep-t8.json` (KiB): the structures from before the index, 6,144 (plan tables about 4,000, queries about 2,000); first-round streams 15,894 and `docs` 15,553 (8 chunks of 22.2 MB); 70% of the rows, 7,414; 8 offset arrays, 1,656. Together 46,661 KiB, 1.9 MiB below the sampled anonymous peak of 48,592 KiB (thread buffers, phrase hits and the first second-round streams); with about 3,300 KiB of file pages the lockstep VmHWM is 51,388 KiB. At the end of the index the anonymous RSS is 43,392 KiB (8 threads) and 45,572 KiB (12 threads), 39,380 and 41,576 KiB after the scan tables are dropped, and 41,944 and 44,432 KiB after the answers.

On the 12-thread box the first round should look like this host's 8-thread lockstep run plus four more offset arrays (about +0.8 MiB). The second round is at most 50,717 KiB of anonymous memory if all 12 second-round sorts coincide exactly (all lists 22,209, rows 10,592, 24 offset arrays 4,968, second-round streams 6,804, before-index 6,144); on this host it reached 47,668 KiB (12 threads, lockstep) and about 47,000 KiB (8 threads).

## Paired results vs the `b7c4ae5` baseline

1 warmup plus 21 measured runs per binary, alternating (`reports/final-t*.json`). Deltas are medians of per-pair ratios; wins counts pairs where the candidate was faster.

| Report | Threads | Cand wall ms | Base wall ms | Paired wall | Wins | Paired CPU | Max RSS cand / base KiB | Paired RSS |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `final-t12.json` (12 threads on 8 vCPUs) | 12 | 189.1 | 195.3 | **-1.93%** | 16/21 | -2.29% | 49,244 / 67,956 | -27.1% |
| `final-t8.json` | 8 | 177.4 | 179.6 | **-1.24%** | 14/21 | -1.30% | 49,444 / 62,632 | -21.1% |
| `final-t6.json` | 6 | 193.9 | 214.4 | **-8.69%** | 19/21 | +0.48% | 50,388 / 61,972 | -18.6% |

Instrumented memory runs, 7 per binary, alternating (`reports/mem/prof-free-t*.json`, `prof-lockstep-t*.json`), median VmHWM in KiB:

| | 8 threads free | 8 threads lockstep | 12 threads free | 12 threads lockstep |
| --- | ---: | ---: | ---: | ---: |
| baseline | 62,996 | 62,728 | 66,916 | 68,056 |
| candidate | 49,436 (-21.5%) | 51,388 (-18.1%) | 49,452 (-26.1%) | 50,652 (-25.6%) |

Screening runs of the steps (11 pairs each vs the baseline, `reports/screen-step*.json`): step 1 -0.09% / +2.17% wall at 8 / 12 threads with 60,236 / 57,172 KiB; step 2 +0.23% / +0.59%, 55,284 / 53,396 KiB; step 3 -1.86% / -3.25%, 53,288 / 50,476 KiB; step 5 -1.07% / -2.62%, 50,080 / 49,240 KiB.

## K estimate

K = (Tref/T)^0.5 x min(50, Mref/M)^0.2 x min(1, Sref/S)^0.15, so the factor is (M_new/M_old)^-0.2 x (T_new/T_old)^-0.5 x (S_new/S_old)^-0.15.

- **M.** The board M of the baseline, 73.8 MB (72,070 KiB), is 4,014 KiB above this host's 12-thread lockstep VmHWM of the instrumented baseline (68,056 KiB); tmpfs output and kernel memory are part of that difference. Adding the same 4,014 KiB to the candidate's 50,652 KiB gives about 56.0 MB, a ratio of 0.759 and a factor of **1.057**. The ratio of the uninstrumented 12-thread medians (0.725) gives 1.067. If on the box all 12 second-round sorts coincided exactly (50,717 KiB anonymous, above), the ratio would be about 0.805 and the factor 1.044.
- **T.** The 8-thread paired wall (-1.24%; 8 threads on 4 cores x 2 SMT is the closest local match to 12 threads on 6 cores x 2 SMT) gives 1.006; assuming no change on the box gives 1.000.
- **S.** +7 lines locally; on the board's count, 583 to about 590, a factor of 0.998.

Estimate: 1.057 x 1.006 x 0.998 = **1.061** (K about 28.7 from 27.00), with a range of about 1.04 to 1.07 from the M and T assumptions above. This is an estimate from local measurements, not a board result.

## Correctness

- Full seed 1: every warmup and measured run in every report produced `f86973c210228141bcb6f1f1b10188ad2a9b65f71e7cd7cf4590b38de4e80927` (asserted by `run.py` and `tools/memrun.py`), and so did the candidate at `SD_THREADS` = 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 16 and 24 (rounds m = 16 down to 1), for both the x86-64-v3 and the portable build.
- `experiments/b-filter-parse/check_all.sh` (20 tiny seeds, sample seeds 2, 3, 4, 5, 7 and the edge fixtures, byte for byte against `official/reference/b_index.py`): pass=34 fail=0 xfail=2 at the default thread count, at 1 and at 12 threads, for the x86-64-v3 and the portable build. The xfails are `edge/no_lf` and `edge/no_lf_docs` (`docs.txt` without a trailing LF, outside spec 2.1), unchanged from the baseline. The new duplicate removal is exercised by real data: a diagnostic build counted 94,137 repeats removed of 11,371,204 list entries on full seed 1 and 4,373 of 381,034 on sample-2 (`edge/repeat` has no list-term entries, its terms get bitmaps). So `experiments/b-linux-profile`'s note that no list term repeats within a document in seed 1 compared counts taken before the removal.
- `RUSTFLAGS='-Ctarget-cpu=x86-64-v3' cargo build --release` and `RUSTFLAGS='-Ctarget-cpu=x86-64' cargo build --release --target-dir /projects/sandbox/.data/tgt-generic` compile without warnings; the portable binary has no ymm instructions.
- Chunk boundaries are still whole lines starting at an id that is a multiple of 64 and still cover the file in order (the weights are positive, so the cuts never decrease); a chunk is at most 1.9 times the old size, and the existing assert still guards the 65,536-document limit of the u16 ids.
- `mallopt` is glibc's; the official image is Debian (glibc). A libc without it would fail to link rather than run differently.

## Files

| File | Content |
| --- | --- |
| `baseline.rs`, `candidate.rs` | sources (SHA-256 above) |
| `profile.rs`, `profile-baseline.rs` | instrumented copies made by `tools/mkmem.py` (SHA-256 `0d40b0bb...` and `f2bb3c75...`), not for production |
| `steps/*.patch` | the measured steps, in order |
| `variants/loo-*.patch` | leave-one-out variants, each against `candidate.rs` |
| `variants/split-*-on-step3.patch` | split ratios against step 3 (test form for m = 2 only) |
| `variants/writev.patch`, `variants/trim-after-index-instead-of-mallopt.patch` | rejected variants against `candidate.rs` |
| `reports/final-t*.json` | final 21-pair `run.py` reports vs the baseline |
| `reports/screen-step*.json`, `reports/loo-*.json`, `reports/loo21-*.json` | screening and leave-one-out `run.py` reports |
| `reports/mem/*.json` | `tools/memrun.py` reports of the instrumented builds (free, lockstep, sampled, trim probes) |
| `reports/*.txt` | console output of `tools/hwm.py` (`chain-hwm`, `split-lockstep`, `loo-lockstep`, `x-lockstep`), `pair.py` (`loo-timing`, `loo21-timing`) and `tools/csrper.py` (`csr-cost`); binary names there are `mem-<variant>` (uninstrumented) and `mem-prof-<variant>` (instrumented) builds: `vA` to `vE` = steps 1 to 5, `final` = the candidate, `vE-noM`, `-noR`, `-noE`, `-noC`, `-noQ`, `-noP` = the leave-one-out variants (mallopt, rounds, early drops, counting sort, query offsets, late drops), `loo-no-rounds` and `loo-old-csr` = the same variants built from the patches, `vC-sAB` = split a:b on step 3, `x-*` = rejected variants |
| `tools/` | `mkmem.py` (instrumentation), `memrun.py`, `hwm.py`, `timeline.py`, `csrper.py`, `tables.py` (report summaries), `sim.py` (lockstep model), `build.sh`, `ab.sh`; paths assume `/projects/sandbox/.data` |

## Reproduce

```sh
D=/projects/sandbox/.data; E=experiments/b-mem; T=$E/tools
# baseline and candidate binaries (build.sh uses a scratch copy of track-b's Cargo files; same binary as in track-b/)
$T/build.sh $E/baseline.rs base-b7c4
$T/build.sh $E/candidate.rs mem-final
for t in "" 1 12; do experiments/b-filter-parse/check_all.sh $D/bin/mem-final $t 2>/dev/null; done
for t in 8 12 6; do $T/ab.sh mem-final 21 $t final-t$t; done        # reports in $D/mem/reports
# instrumented builds and memory reports
python3 $T/mkmem.py $E/baseline.rs > $D/mem/pb.rs && $T/build.sh $D/mem/pb.rs mem-prof-base
python3 $T/mkmem.py $E/candidate.rs > $D/mem/pc.rs && $T/build.sh $D/mem/pc.rs mem-prof-final
for t in 8 12; do
  python3 $T/memrun.py --runs 7 --threads $t --report $D/mem/prof-free-t$t.json mem-prof-base mem-prof-final
  python3 $T/memrun.py --runs 7 --threads $t --env SD_PROF_LOCKSTEP=1 --report $D/mem/prof-lockstep-t$t.json mem-prof-base mem-prof-final
  python3 $T/memrun.py --runs 5 --threads $t --env SD_PROF_TRIM=outs_sort_concat --report $D/mem/prof-base-trimpeak-t$t.json mem-prof-base
done
python3 $T/timeline.py mem-prof-final 12 4 SD_PROF_LOCKSTEP=1    # RSS series and per-chunk times of one run
python3 $T/tables.py $E/reports
for f in $E/baseline.rs $E/candidate.rs; do rustfmt --edition 2021 --emit stdout $f | grep -cvE '^\s*$|^\s*//'; done
```
