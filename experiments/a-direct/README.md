# Track A: output written with O_DIRECT, on top of a-mem (branch a-direct)

**Board result: negative, reverted.** `run-4f0849dc691c` gave T 33.0 ms, M 21.1 MB and K 35.98, against production's best K 42.59 at M of about 22 MB. M did not move because `/out` on the box is tmpfs (next section). Everything after the next section is the record from before the trial. Its numbers come from the local sandbox (8 vCPU Xeon Platinum 8488C, Linux 6.1, `/projects/sandbox` on xfs, `/tmp` and `/dev/shm` on tmpfs, no cgroup memory controller, rustc 1.92.0 with the crate's `x86-64-v3` config) and are not board results.

## Board result

The trial ran once, `run-4f0849dc691c` at `0da83ae` on `speed-demon` (1 Nov 2026), and was reverted in `b4e0d40`: T 33.0 ms, M 21.1 MB, S 512, K 35.98. The second run was skipped because the M result does not depend on run-to-run noise.

M did not move because the official harness keeps outputs on tmpfs:

- `harness/setup-box.sh` (official repo at `ad1f060`) mounts `/srv/speeddemon/work` as `tmpfs size=8g`, with the comment "outputs live on a capped tmpfs so no run can fill the disk".
- `harness/run_submission.py` bind-mounts `<work>/<run_id>/out` as `/out`.
- `harness/README.md` says `memory.peak` counts tmpfs.

The box's kernel may refuse `O_DIRECT` on tmpfs (this code then takes its buffered fallback) or accept it. Either way the written bytes are shmem pages charged to the run's cgroup. So the output is part of M, as assumed below, but `O_DIRECT` cannot take it out of M on the box. The harness source shows this, and it should have been checked before the trial.

What this means for Track A:

- All 10.11 MB of `summary.txt` is charged at exit, so it is a floor under M, and the 4.48 MB cap is out of reach.
- Only the memory still resident while the output is complete can be cut: tables, arenas and buffers not yet given back when the last hours are written. That is about 10 to 12 MB on top of the output: production is at about 22 MB, a-mem at 20 to 21 MB and this run at 21.1 MB.
- With everything but the output released before the last hours are written, M might reach about 14 to 15 MB. That is at most about +7.7% K, (21 / 14.5)^0.2, before the S cost of the extra code.

T: with the output on tmpfs, the path the box took, this code costs little locally. These are paired medians over 31 rounds; only the printed medians were kept, not the samples:

| Output on tmpfs | 12 threads | 8 threads |
|---|---:|---:|
| candidate / a-mem | 1.014 | 1.037 |
| candidate / production | 0.895 | 0.938 |

The board's 33.0 ms is well above that (a-mem ran 25.3 and 26.9 ms on the board). Without a production run in the same window, it is unclear whether the window was slow or the cost is specific to the box.

## Why

`summary.txt` is 10.11 MB. A buffered write leaves all of it in the page cache, and page cache written by the run is charged to the run's cgroup, so it counts toward M. The board figures fit that:

- Production A (`speed-demon` `5eaefdc` src) holds every record until the parse ends and writes the output afterwards. Board M is about 22 MB: the best run's K and T (`run-713461e1b8d4`, K 42.59, T 24.86 ms, S 414) imply 21.7 MB, and the probes on the same source measured 22.7 to 23.1 MB (`experiments/a-box-probes/BOARD.md`). The local estimate below (peak of anonymous memory plus the output written so far) is 19.9 MB at the board's 12 threads.
- PR #30 (`a-mem`) cut local peak anonymous memory from 16.6 to 8.5 MB at 12 threads, yet board M stayed at 20.05 and 20.96 MB (`run-3d499d7c63a1`, `run-69ed99a53619`). Its local peak comes near the end of the run, when most of the output has been written: est M 17.6 MB at 12 threads against 8.5 MB of peak anonymous memory.

So the output is a large part of M, about half of it for a-mem, and PR #30's note that "the 10.1 MB output counts toward M, so the 4.56 MB cap is unreachable" holds only for buffered writes. Written with `O_DIRECT`, the data goes from the buffer to the device and nothing of the file stays in the page cache. With that, a-mem's lower anonymous memory reaches the board's M.

At the current M of about 22 MB, the cap (Mref / 50, about 4.3 to 4.6 MB) is about 5 times lower, so M is still the largest lever left in K = (Tref/T)^0.5 x min(50, Mref/M)^0.2 x (Sref/S)^0.15: halving M is worth as much as cutting T by 24%.

## Change

`candidate.rs` is `a-mem.rs` (`track-a/src/main.rs` of branch `a-mem`, PR #30) with one new type, `Out`, which replaces the `fs::File` that the workers write to under the `out` mutex:

- `Out::open` creates `summary.txt` with `O_DIRECT` (`0o40000`, through `OpenOptionsExt::custom_flags`). If the file system refuses it (tmpfs returns `EINVAL` on this sandbox's Linux 6.1; kernels that accept it on tmpfs keep the data in memory anyway), it opens the file without the flag. Both cases then run the same code. `0o40000` is `O_DIRECT` on x86-64, the scoring box; on aarch64 the same bit is `O_DIRECTORY`, so there the first open fails or gives an ordinary buffered file, with the same output.
- `put` copies an hour's lines into a 1 MiB staging buffer that starts on a 4 KiB boundary inside a `Vec` of 1 MiB + 4 KiB. `flush` writes the buffer whenever it is full, so every write is 4 KiB-aligned in memory, length and file offset, as `O_DIRECT` needs.
- The last `flush` pads the final block with zeros, writes it and cuts the file to its real length with `set_len`. Each `flush` calls `set_len` (10 calls on seed 1).
- The first, early-closing run and the rerun each create `summary.txt` afresh (truncate), as before.

No `unsafe`, no new C call, no allocator setting. `baseline.rs` is production `track-a/src/main.rs` on `speed-demon` (`5eaefdc` src, SHA-256 `ce046389...e118`); `a-mem.rs` has SHA-256 `bc534081...40ae`; `candidate.rs` (= `track-a/src/main.rs` on this branch) has SHA-256 `46e27c6a...4acb`. S (`experiments/b-mem2/tools/sloc.py` of branch `b-mem2`: rustfmt'd code lines plus Dockerfile lines) is 407 + 7 = 414 for production, 461 + 7 = 468 for a-mem and 505 + 7 = 512 here. The `Out` type is 43 lines; the rest is one import line and the final `flush` call, less one line where `run` created the file.

## Measurements

Tools in this folder; outputs on xfs (`/projects/sandbox/.out`), where `O_DIRECT` is taken. Every output in every run matched the published full seed-1 SHA-256 `495ca096...1cd3`.

`memrun.py`: 21 rounds after one warm-up per binary, the three binaries in random order each round (`reports/memrun-t{12,8}.json`). anon is the sampled peak of RssAnon + RssShmem + VmPTE. est M adds the output written so far times the fraction of the file `fincore` reports resident after the run (100% for buffered writes, 0% here).

| Threads | | production | a-mem | candidate |
|---:|---|---:|---:|---:|
| 12 | median wall | 45.6 ms | 39.3 ms | 41.3 ms |
| | anon | 16.59 MB | 8.52 MB | 9.76 MB |
| | est M | 19.87 MB | 17.59 MB | **9.76 MB** |
| | output resident after the run | 100% | 100% | 0% |
| 8 | median wall | 37.7 ms | 34.0 ms | 35.8 ms |
| | anon | 15.61 MB | 6.51 MB | 7.65 MB |
| | est M | 17.93 MB | 16.03 MB | **7.65 MB** |

The candidate's extra 1.1 to 1.2 MB of anonymous memory over a-mem is mostly the 1 MiB staging buffer.

`pairs.py`: 31 rounds after one warm-up each, both binaries in random order each round (`reports/pairs-*.json`); the median of the per-round ratios candidate / base, and in how many rounds the candidate was faster:

| Threads | vs production | vs a-mem |
|---:|---:|---:|
| 12 (oversubscribed here) | 0.9150 (28/31) | 1.0524 (5/31) |
| 8 | 1.0136 (10/31) | 1.0632 (2/31) |

So `O_DIRECT` costs about 5 to 6% of wall time here against a-mem: the writes are synchronous, and a worker that finishes a later hour waits under `turn` while an earlier hour's `flush` reaches the device. The cost on the board depends on its disk, which is unknown.

`reports/measure.txt` holds the printed tables. An earlier measurement of the same code before a comment-only edit gave the same picture (est M 9.71 MB at 12 threads, paired 1.0418 and 1.0729 against a-mem).

## What the board run decides

The board's production figures: T about 25 ms (best `run-713461e1b8d4`, 24.86 ms, K 42.59), M about 22 MB, S 414. Board M ran about 1.8 to 3.2 MB above the local est M for production and 2.5 to 3.4 MB above it for a-mem, so the candidate's board M should be about 11.6 to 13.2 MB if the output is charged to the cgroup as page cache. The table takes T0 = 25 ms, M0 = 22 MB, S 414 to 512 and the candidate's T 5% above production's, as here against a-mem (a-mem itself ran at production's T on the board).

| Board M | K ratio at T + 5% | break-even board T (keep rule T1/T0 < (M0/M1)^0.4 x (S0/S1)^0.3) |
|---:|---:|---:|
| 11.6 MB | 1.074 | 30.3 ms |
| 13.2 MB | 1.047 | 28.8 ms |
| about 20.5 MB, a-mem's (hypothesis wrong) | 0.959 | below production |

- **M falls to about 12 to 13 MB:** the hypothesis holds. Keep the change if T stays below the break-even. Then the next steps are trimming a-mem's anonymous memory (three scratch sets instead of four, `cap3` in `experiments/a-mem` on branch `a-mem`; a 512 KiB stage), and taking the `flush` off the waiting workers' path if the board shows a large T cost.
- **M stays at about 20 MB:** `/out` refuses `O_DIRECT` (tmpfs), or the output is not what the board charges. Revert.
- **The run fails:** one failure invalidates the track, so this has to pass on the board before it can stay. A file system that accepts `O_DIRECT` at open but refuses aligned writes would panic in `flush` with "write summary.txt". The open-time fallback covers tmpfs; there is no write-time fallback.

## Correctness

`reports/checks.txt` for the candidate binary (`97a63af6...ba8b`, built from `candidate.rs` and also measured above):

- `experiments/a-x86-speed/check.py`: full seed-1 hash at `SD_THREADS` 1, 2, 3, 6, 8, 12, 20, 64 and the default count; `track-a-verification/test.py`, `page_end_test.py`, `latency_grid_test.py`; sample seeds 2, 98, 999 and 4242 byte-identical to the official reference. The helper suites ran twice: with `TMPDIR` on xfs (`O_DIRECT`) and on tmpfs (the buffered fallback).
- `experiments/a-x86-speed/adversarial.py --spec`: 0 failures, on xfs and on tmpfs.
- `order_test.py` (a copy of `experiments/a-mem/order_test.py` from branch `a-mem` with a `--tmp` option for the output file system): original, sorted, shuffled, first-to-end, last-to-start, one-hour-late, two-hours-late and empty logs at 1, 3, 8, 12 and 20 threads, 40 of 40 on xfs and 40 of 40 on `/dev/shm`. The shuffled and moved-line cases take the rerun, so the rerun's truncate-and-rewrite is covered on both paths.
- Full seed 1 written to tmpfs (fallback): the published hash. After a run on xfs, `fincore` reports 0 resident pages of the 9.6 MiB output.

Docker does not work in this sandbox (podman has no `conmon`), so `check.py` (the container check) was not run. The Dockerfile is unchanged.

## Files

- `baseline.rs`, `a-mem.rs`, `candidate.rs`: the three sources measured.
- `memrun.py`, `pairs.py`: the memory and paired-time tools above; `order_test.py`: line-order and fallback check.
- `reports/`: JSON samples, `measure.txt`, `checks.txt`.
