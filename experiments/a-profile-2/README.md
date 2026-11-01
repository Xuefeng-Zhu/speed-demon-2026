# Track A profile at 98c96ce (after PR #9): allocator mmap-lock stalls

`base.rs` is production `track-a/src/main.rs` at `speed-demon` 98c96ce. `timed.rs` adds phase timers, per-thread CPU clocks, per-thread context switches (`RUSAGE_THREAD`) and per-job summary timings on stderr; the algorithm is unchanged. `phases.py` runs it and writes `phases.json`. `mem-*.rs` add a 100 µs `RssAnon` sampler thread. All numbers are from the local x86 VM (8 vCPU Xeon Platinum 8488C, 4 cores x 2 hyperthreads); they are not official scores. 20 threads oversubscribes this VM.

## Phases (medians, ms from the start of `main`)

| Threads | Parse first / median / last thread done | Barrier | Plan done | Summary first / last worker done | End of main | Driver wall |
|---:|---|---:|---:|---|---:|---:|
| 8 | 18.1 / 19.1 / 20.1 | 20.2 | 20.3 | 26.8 / 27.5 | 27.7 | 30.0 |
| 12 | 18.7 / 23.0 / 24.9 | 24.9 | 25.1 | 33.1 / 34.2 | 34.8 | 37.3 |
| 20 | 18.4 / 24.1 / 27.5 | 27.6 | 27.7 | 36.1 / 38.2 | 40.0 | 42.3 |

- **Process CPU:** user 147 ms and sys 31 ms at 8 threads. Sys grows to 52 ms at 20 threads.
- **Per-thread CPU at 8 threads:** a parse thread's CPU clock reads at most 17.2 ms, but it takes 18 to 20 ms of wall time. A summary worker uses 4.7 ms of CPU across a 6.2 ms summarize span.
- **Context switches:** parse threads together make about 600 voluntary context switches at 8 threads, and summary workers about 240. None of them wait on locks of ours: the job-queue lock wait is 0.00 ms and each worker's channel sends total 0.27 ms. The waiting matches the process's memory-map lock instead. Every allocation of 128 KiB or more is its own mmap (the 72 hour buffers per parse thread, the 256 KiB output buffers, `lat`), and every free is a munmap. Both take the lock for writing, and each page fault in any other thread waits for it.
- **Startup:** the spawn of the parse threads begins 0.3 ms into `main` when `/out/summary.txt` does not exist. Locally it began at 2.4 ms when an earlier 10 MB `summary.txt` was being truncated on xfs; `bench.py` deletes the file before every run, so its numbers are not affected.

## Allocator settings (kept)

`mallopt` with `M_MMAP_THRESHOLD = 32 MiB`, `M_TOP_PAD = 32 MiB` and `M_TRIM_THRESHOLD = i32::MAX` keeps every buffer in the malloc heap, so there are almost no mmap or munmap calls. On its own this raises peak anonymous memory by 6 to 11 MB, because freed buffers stay resident. `release` puts that back by calling `MADV_DONTNEED` (which needs the lock only for reading) on the whole pages of each record buffer and each output buffer right before it is freed.

Context switches with all three settings (`timed-mallopt.rs`, 8 threads): parse threads 607 to 165, summary workers 251 to 14. Sys time fell from 35 to 23 ms, parse CPU from 132 to 121 ms, and the end of main from 26.9 to 23.1 ms.

Sampled peak `RssAnon` (`mem-*.rs`, 9 to 11 runs, max / median):

| Variant | 8 threads | 12 threads | 20 threads |
|---|---|---|---|
| base | 15.0 / 14.7 MB | 16.6 / 15.8 MB | 18.6 / 17.7 MB |
| `M_MMAP_THRESHOLD` only (`m-thr`) | 19.7 / 18.6 MB | | 29.3 / 27.3 MB |
| all three (`m-all`) | 24.0 / 21.2 MB | | 30.2 / 29.6 MB |
| all three plus `M_ARENA_MAX = 1` (`m-all-a1`) | 20.6 / 19.8 MB | | 26.3 / 24.5 MB |
| all three plus `release` (`m-all-dn`) | 16.7 / 15.9 MB | | 19.6 / 19.2 MB |
| production (`final.rs`) | 16.2 / 15.8 MB | 17.5 / 16.5 MB | 20.0 / 19.2 MB |

Speed, `bench.py` paired median ratio against `base` (below 1 is faster):

| Variant | 8 threads | 12 threads | 20 threads | Default (8 here) | Report |
|---|---:|---:|---:|---:|---|
| `m-thr` | 0.9281 | 0.9219 | 0.9179 | | `bench-mallopt.json` (41 rounds, seed 1101) |
| `m-all` | 0.8775 | 0.8469 | 0.7535 | | `bench-mallopt.json` |
| `m-thr-a1` | 1.0144 | 0.9200 | 0.8427 | | `bench-mallopt.json` |
| `m-all` | 0.8743 | 0.8433 | 0.7425 | | `bench-dn.json` (41 rounds, seed 1102) |
| `m-all-dn` | 0.8714 | 0.8432 | 0.7374 | | `bench-dn.json` |
| `m-all-dn` repeat | 0.8699 | 0.8495 | 0.7372 | 0.8587 | `bench-dn-2.json` (61 rounds, seed 1103) |
| production `final.rs` | 0.8776 | 0.8347 | 0.7267 | | `bench-final.json` (41 rounds, seed 1104) |

The gain grows with the thread count because each mmap or munmap stalls more faulting threads. The scoring box runs 20 threads by default, which may explain why the earlier box speedup (PR #4, about 16%) fell short of the local 8-thread estimate (about 22%).

Correctness of production: `check.py` 14 of 14, `adversarial.py` 0 failures, and the scalar (no AVX2) build passes `adversarial.py --quick` with 0 failures. The source grows from 467 to 483 code lines (`experiments/a-trim/sloc.py`).

## Rebased on the trimmed source (171ca6f)

`base-trim.rs` is production at `171ca6f` (PR #10 line trim applied); `final-trim.rs` is the same change rebased onto it, the only conflict being the removed `PAIRS` table. `adversarial.py` is brought over from the `a-trim` branch for its `--spec` mode, since the trimmed source stops on inputs outside the spec.

- Correctness: `check.py` 14 of 14; `adversarial.py --spec` 0 failures, for both `base-trim` and `final-trim`.
- Code lines (`experiments/a-trim/sloc.py`): 407 to 423. The board counted 414 for `171ca6f`, about 7 more than this script, so expect about 430.
- Speed, paired median `final-trim` / `base-trim`: 0.8513 / 0.8373 / 0.7352 at 8 / 12 / 20 threads (41 rounds, seed 1201, `bench-trim.json`), and 0.8649 / 0.8383 / 0.7276, 0.8819 at the default thread count (61 rounds, seed 1202, `bench-trim-2.json`).
- Sampled peak `RssAnon` (11 runs, max / median): 8 threads 15.1 / 14.7 to 17.1 / 15.9 MB; 12 threads 16.2 / 15.8 to 17.8 / 16.5 MB; 20 threads 17.8 / 17.1 to 20.5 / 19.3 MB.
