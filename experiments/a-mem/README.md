# Track A memory: hours closed and written while the log is parsed (branch a-mem)

**Board run pending.** Every number here comes from the local sandbox (8 vCPU Xeon, Linux 6.1, THP `madvise`, no cgroup memory controller). None of them are board results. The board figures for the baseline (`f828bd8`) are about T 24.8 ms and M 22.3 MB, S 414.

`baseline.rs` is `track-a/src/main.rs` at `speed-demon` `f828bd8`. `candidate.rs` is `track-a/src/main.rs` on `a-mem`. `variants/` holds the rejected variants, each a full source file.

## Which M to estimate

Board M is a cgroup peak. It charges anonymous memory, page tables and the 10.11 MB `summary.txt` on tmpfs. The input pages are mmapped and pre-warmed, so they are not charged. The round-4 estimate (peak anonymous RSS plus the final output size, `est M`) adds two peaks that do not happen at the same time. For the baseline it gives 25.1 MB at 8 threads and 28.1 MB at 20 threads. `memrun.py` here is a copy of the round-4 tool with one addition: **live M**, the peak over samples of RssAnon + RssShmem plus the output file's size at that same moment. The board runs 12 threads. The i5-13500 has 20 hardware threads (6 P-cores with hyperthreading plus 8 E-cores), but the harness starts every timed container with `--cpuset-cpus=0-11` (the P-cores; `run_submission.py --cpuset` and `final_scoring.py --run-cpuset` both default to `0-11`, and the harness README lists "6 P-cores and 12 threads"), so `available_parallelism` reports 12. For the baseline at 12 threads live M is 19.24 MB (median of 21 runs), about 3 MB below the board's 22.3 MB. At 20 threads it is 22.49 MB, which matched the board's figure only by coincidence, and at 8 threads 17.05 MB. The 20-thread columns below are kept as an oversubscription check. The rest of this README uses live M and gives est M next to it.

## Baseline breakdown

Tools: `instrument.py` adds a 100 µs sampler (RssAnon, output size so far, VmPTE). `make-profile.py base` adds per-structure residency read from `/proc/self/pagemap`, plus a `/proc/self/smaps` split between the threads' malloc arenas (heaps aligned to 64 MiB) and other anonymous mappings. Outputs are in `reports/tsb-t{8,20}.txt` and `reports/pbd-t{8,20}.txt`.

| Structure | 8 threads | 20 threads |
|---|---:|---:|
| Anonymous RSS at the barrier after parsing | 14.0 MB | 16.8 to 17.0 MB |
| Record buffers (72 hour buckets per thread, mapped, 4 bytes per line) | 13.0 MB resident (12.1 MB of records) | 13.2 MB |
| Endpoint tables (one per thread; the name arena grows by doubling in the thread's heap) | 8 x 136 KB = 1.09 MB | 20 x 138 KB = 2.76 MB |
| Thread malloc arenas, in total (tables, names, map nodes, freed growth copies) | 1.57 MB | 5.22 MB |
| Shared name maps (1,842 copies) | 0.13 MB | 0.13 MB |
| Thread stacks (touched) | about 0.1 MB | about 0.2 MB |
| Summary scratch (`lat` for the hour's latencies, counts), kept by every worker | 8 x 0.31 MB = 2.48 MB | 20 x 0.28 MB = 5.69 MB |
| Output buffers waiting in the main thread for an earlier hour (largest) | 2.05 MB | 6.99 MB |
| Live peak (anonymous + output so far) | 17.2 MB at 33 ms: 10.7 + 6.1 | 23.2 MB at 50 ms: 14.9 + 8.3 |

So the baseline peak is all of the log's records held at once (13 MB). The live peak itself comes partway through the summary phase. By then about half the records are freed, but every worker's scratch, the output buffers that wait for a slow earlier hour, and the output written so far are all live. Thread count adds about 0.3 MB per thread to the tables and arenas and about 0.3 MB per summary worker. The output buffers in the process do not duplicate the whole output: each one is freed right after its hour is written. Only the buffers waiting behind an earlier hour are duplicated, and that is up to 7 MB at 20 threads.

## Candidate

1. **Hours are closed during the parse.** The log is cut into about 512 KiB newline-aligned chunks, and threads take them in file order. Once every chunk up to some point is parsed, every hour before the latest hour seen there, except the last one, is closed and queued. In the generator's logs no record is more than an hour behind an earlier one: shard 0 uploads each hour 5 to 10 minutes after it ends, and seed 1 has no line more than one hour behind the running maximum. If a record arrives for a closed hour anyway, the run starts over without early closing (`run(.., early = false)`). That rerun is the old algorithm: summaries start after the last chunk. So the output is correct for any line order, and only out-of-order logs pay for a second pass.
2. **Threads take queued hours before chunks**, at most four hours at a time. They format into the summary scratch's own output buffer and write each hour once the hours before it are written. Those hours are already being summarized, so a write waits at most for a few summaries. There is no main-thread writer and no queue of pending output buffers.
3. **Buffers are reused, not freed, while more will be needed.** Freeing a mapped buffer raises glibc's dynamic mmap threshold, so later 128 KiB record buffers would come from the threads' heaps, where freed memory stays resident (anonymous RSS grew steadily to 9 MB in the first, freeing version). Instead, record buffers go back to a spare pool once their hour is summarized, and output and `lat` buffers stay in the four scratch sets. The pool is dropped when the last chunk is taken, and a scratch set is dropped when no hour is left, so both are gone before the last hours are written. The table's name arena is reserved at 128 KiB up front (mapped, no growth copies left in the heap), and the table slots are `u32`.
4. **No allocator settings.** There is no `mallopt`, top pad or trim threshold, and no `MADV_DONTNEED` on buffers (`parse` still drops the finished input pages with it, as the baseline does). Every big buffer is a plain `Vec` of at least 128 KiB, mapped by glibc's default threshold.

Candidate breakdown (`reports/pcd-t{8,20}.txt`, `reports/tsc-t{8,20}.txt`), shortly before hour 60 is written at 8 threads (live peak 15.0 MB at 30 ms: 5.7 anonymous + 9.3 output): anonymous 6.7 MB = held records 0.46 + spare record buffers 1.88 + scratch sets 0.92 + tables 8 x 116 KB = 0.93 + thread arenas 1.80 (slots, escaped-record vectors, per-chunk hour vectors, map nodes, the plan) + stacks and the rest. Before the last hour: 3.45 MB. At 20 threads the sandbox is oversubscribed (20 threads on 8 vCPUs): summaries fall behind the parse, up to 16 closed hours are queued, and held records reach 6.3 MB at hour 36. This depends on oversubscription and should not happen on the board's 12 threads.

Line order and fallback (`order_test.py`, against the official reference on reordered copies of sample seed 2, at 1, 3, 8 and 20 threads): original, sorted, one-hour-late and empty need no rerun; shuffled, first-to-end and last-to-start rerun; two-hours-late reruns unless the chunks in between finish together. All 32 cases match (`reports/order_test.txt`; a build that prints on fallback showed which cases rerun).

## Measurements

`memrun.py`, 21 interleaved runs per binary after one warm-up run, with every output hash checked (`reports/memrun-t{8,12,20}.json`). `compare.py` gives the paired median wall ratios and the keep rule T1/T0 < (M0/M1)^0.4 x (S0/S1)^0.3, with M taken as the median live M (the 4.56 MB cap does not bind) and S 414 to 468:

| Threads | T base / cand (ms) | paired T1/T0 (wins) | live M base / cand (MB) | est M base / cand (MB) | break-even T1/T0 | predicted K |
|---:|---|---|---|---|---:|---:|
| 8 | 38.5 / 34.6 | 0.9089 (20/21) | 17.05 / 15.45 | 25.10 / 16.02 | 1.0025 | 1.0502 |
| 12 | 45.6 / 39.5 | 0.8683 (21/21) | 19.24 / 16.92 | 26.23 / 17.75 | 1.0147 | 1.0810 |
| 20 | 52.7 / 47.8 | 0.9120 (19/21) | 22.49 / 19.46 | 28.07 / 20.97 | 1.0213 | 1.0582 |

Predicted K = (T0/T1)^0.5 x (M0/M1)^0.2 x (S0/S1)^0.15. At 12 threads, the board's count, M falls 12.1% (19.24 to 16.92 MB). That pays for 54 more lines as long as board T does not rise by more than 1.5% (break-even 1.0147). At equal T, K rises 0.7% ((M0/M1)^0.2 x (S0/S1)^0.15 = 1.0073). If the 3 MB between local live M and the board's 22.3 MB is a fixed offset (22.3 to 19.98 MB), the break-even is 0.7% and the equal-T gain 0.4%. At 20 threads the same arithmetic gives a 2.1% break-even and +1.1% at equal T (an earlier version of this README said +2.2% at equal T; that was wrong, 2.1% is the T break-even).

Line order: the early close uses the generator's shard model (shard 0 uploads 5 to 10 minutes after the hour, so about 50 minutes of margin) for speed only. The spec promises no bound on disorder, and none is assumed for correctness: hours close only on the merged prefix, every merge checks for late records under the state lock, and a late record reruns the old algorithm.

The local speedup (9 to 13%) comes from the dynamic chunk queue and from summaries running during the parse. The board may not repeat it: PR #19 and PR #21 were both faster locally but not on the board. The board's 12 threads are 6 P-cores with hyperthreading, so the queue cannot gain from balancing E-cores there, and the extra locks could cost time. If board T rises by more than about 1.5%, the change does not pay for its lines, and the local gain at equal T is small (0.4 to 0.7%), so the trial mainly tests whether the local speedup carries over.

S (`sloc.py`): 461 + 7 = 468, up from 407 + 7 = 414. The new code is the chunk queue, closing and fallback state, the plan cache and the in-order writer. Two attempts to save lines were measured and rejected; see below.

## Rejected variants

Local screens: 11 interleaved runs per binary against the candidate (`reports/variants-t{8,20}.json`), plus earlier screens of 5 to 7 runs during development. At 8 threads the sandbox is not oversubscribed, so those are the cleaner T readings.

| Variant | 8 threads T / live M | 20 threads T / live M | Verdict |
|---|---|---|---|
| candidate | 34.6 ms / 15.45 MB | 49.9 ms / 19.17 MB | |
| `cap2`, `cap3`: two or three scratch sets | 35.2 / 14.79; 34.6 / 15.09 | 53.6 / 18.24; 48.0 / 18.30 | cap 2 is slower at 20 threads. Cap 3 is about 0.4 to 0.9 MB lower at the same local T, but leaves less summary headroom. It is the first follow-up to try on the board |
| `cap6` | 35.5 / 16.45 | 47.2 / 20.46 | more memory |
| `dontneed-all`: `MADV_DONTNEED` on every returned record buffer | 38.9 / 14.73 | 50.0 / 17.35 | +12% T at 8 threads |
| `dontneed-cap16`: the same once 16 buffers are spare | 38.6 / 14.88 | 50.0 / 17.66 | +12% T at 8 threads |
| `shared-names`: table entries point at the shared name copies (48 KB tables instead of 116 KB) | 36.3 / 15.12 | 49.4 / 18.50 | +5% T at 8 threads (one more dependent load per line); 5 more lines |
| `state-writer`: write under the state lock, no second condvar (4 fewer lines) | 35.8 / 15.49 | 50.4 / 18.33 | +3.5% T at 8 threads |
| freeing record and output buffers instead of pooling them (first version, 1 MiB chunks) | 35.6 / 19.03 | (12 threads) 40.1 / 21.30 | anonymous RSS grows through the run as freed buffers come back from the heaps |
| main-thread writer with an output buffer pool (before the in-order writer) | 36.1 / 15.93 | 44.3 / 19.94 | replaced: more lines and pending buffers |

## Correctness

The candidate (`track-a`, `RUSTFLAGS='-Ctarget-cpu=native' cargo build --release`) matches the published full seed-1 SHA-256 `495ca096...1cd3` at `SD_THREADS` 1, 2, 3, 5, 8, 12, 16, 20 and 64, at the default thread count, and in every measured run. Other checks:

- `smallcheck.py a` (tiny and sample, seeds 2 and 7, against the official reference) at 1, 3, 8 and 20 threads.
- `track-a-verification/test.py --io directories` (its random-order inputs take the fallback), `page_end_test.py` (14 of 14) and `latency_grid_test.py` at 1 to 64 threads.
- `experiments/a-x86-speed/adversarial.py --spec`: 0 failures.
- `order_test.py`: 32 of 32.

## Files

- `memrun.py`: round-4 sampler with live M; `compare.py`: paired ratios and the keep rule.
- `instrument.py`, `make-profile.py`, `profile-helpers.rs`: the profiling copies; `build.sh SRC NAME` builds one in a scratch crate.
- `order_test.py`: line-order and fallback check.
- `reports/`: memrun JSON, profile outputs and the order test log.
