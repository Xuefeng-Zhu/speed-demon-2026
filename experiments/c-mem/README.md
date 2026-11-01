# Track C memory trim (round 4, branch `c-mem`)

Sandbox measurements (8 vCPU Xeon, kernel 6.1, THP=madvise), not board results. Board run pending.

Goal: lower Track C's peak memory (board M about 11.4 MB, capped score at Mref/50 = 7.35 MB) under the
keep rule T1/T0 < (M0/M1)^0.4 x (S0/S1)^0.3. Baseline is speed-demon `f828bd8` (`baseline.rs`,
S 328+8 = 336, binary `/projects/sandbox/.data/bin/base-c`).

## Candidate (`candidate.rs` = `track-c/src/main.rs`)

Three changes, S 336 -> 337 (+1 line):

1. `BLOCK` 1024 -> 256 events per inbox block (each producer keeps n partly filled blocks, one per owner).
2. `pread` buffer 64 KiB -> 32 KiB per worker (it still doubles when one record fills it).
3. Each worker empties its own inbox (`mark`) at every buffer refill, not only after each chunk.

## Memory breakdown of the baseline

Tools: `make-variants.py` writes `profile.rs` (and `variants/profile-*.rs`), an instrumented copy with an
`SD_THREADS` override that prints, per phase, VmHWM / RssAnon / AnonHugePages, glibc `mallinfo2`
(arena size, in use, free), the inbox backlog high-water mark (events queued but not yet marked), the
anonymous mappings over 64 KiB at the end of the workers, and the peak anonymous RSS per stage from an
in-process `/proc/self/statm` sampler (stages: setup, parse, last chunks, final marks after every block
was sent, after the workers). Raw output: `reports/cm-profile.txt` (baseline) and
`reports/cm-profile-mark-blk256-buf32.txt` (candidate), 3 runs each at 8, 12 and 20 threads.

| item | 8 threads | 12 threads | 20 threads |
|---|---|---|---|
| name tables `5 * m * n` words (2^17 slots, 40 B each, fully touched) | 5.24 MB | 5.24 MB | 5.24 MB |
| region table (one byte per id up to 999,993) | 1.00 MB | 1.00 MB | 1.00 MB |
| inbox backlog high-water mark (8 B per event) | 0.17-0.22 M events = 1.4-1.8 MB | 0.26-0.36 M = 2.1-2.9 MB | 0.32-0.36 M = 2.6-2.9 MB |
| producers' blocks `n * n * BLOCK * 8` | 0.5 MB | 1.2 MB | 3.3 MB |
| `pread` buffers `n * 64 KiB` | 0.5 MB | 0.8 MB | 1.3 MB |
| malloc arenas during the parse (size / in use) | 3.5 / 2.0 MB | 6.5 / 3.9 MB | 11.8 / 6.6 MB |
| peak anonymous RSS, sampler (memrun est. M) | 9.4-9.7 MB (9.3-9.6) | 12.0-12.7 MB (12.6-12.8) | 17.1-17.3 MB (17.5-17.6) |

* The backlog is the largest variable item. Owners only marked after finishing a chunk (1/16 of a
  worker's share, about 1.6 MB of input at 8 threads), so every other producer's events for them piled up
  meanwhile: about n x one chunk's events, which does not shrink with more threads.
* The peak is reached at the end (final marks after the barrier), when every producer's partly filled
  blocks are also handed over.
* Freed blocks stay in the per-thread malloc arenas (`fordblks` 1.2-3.0 MB after the workers), so the
  arena high-water mark is what counts. Each worker's arena keeps at least about 150 KB resident after
  its frees (the 128 KiB top pad plus headers), visible in the smaps listing.
* The two tables are adjacent anonymous mappings with the same flags, so the kernel merges them into one
  6,104 KiB VMA; with MADV_HUGEPAGE at most one aligned 2 MiB huge page fits (AnonHugePages 0 or
  2,048 KiB; it is sometimes faulted in while the region table is filled, hence the 2.2 MB "setup" stage
  in some runs). Both tables end fully touched, so huge pages do not round the peak up; dropping
  MADV_HUGEPAGE changed nothing measurable (variants `nohuge-region`, `nohuge`).
* Thread stacks: only touched pages count; 256 KiB stacks (`stack`) changed nothing. The ring (16
  entries of 48 B) is negligible.

Candidate at the same points: backlog high-water 30-37 k events at 8 threads (about 0.1 M at 12 and
20 threads, where the sandbox is oversubscribed and owners get descheduled), producers' blocks 0.13 /
0.3 / 0.8 MB, buffers 0.26 / 0.4 / 0.65 MB. Peak anonymous RSS 7.4-7.5 / 8.7-9.0 / 11.6-12.0 MB; what
remains above the 6.24 MB of tables is mostly malloc arenas (about 200 KB per worker at the end).

## Screened variants

`make-variants.py` generates every variant from `baseline.rs` (all with the `SD_THREADS` override, also
`variants/base.rs` = `cm-base`), `build.sh SRC NAME` builds one natively. `memrun.py` (round-4 tool,
interleaved runs, est. M = peak RssAnon+RssShmem + output size), summaries by `compare.py` in
`reports/summary.md` (break-even uses M capped at 7.35 MB and S per variant). Est. M in MB, wall paired
ratio against `cm-base` in the same batch (7-9 runs per batch):

| variant | S | 8 thr M / T1/T0 | 12 thr M / T1/T0 | 20 thr M / T1/T0 |
|---|---|---|---|---|
| base | 336 | 9.48 / 1 | 12.64 / 1 | 17.48 / 1 |
| BLOCK 512 | 336 | 9.27 / 1.034 | 11.67 / 1.044 | 14.96 / 0.994 |
| BLOCK 256 | 336 | 9.18 / 1.018 | 11.08 / 1.002 | 13.89 / 0.977 |
| BLOCK 128 | 336 | 9.08 / 1.036 | 11.01 / 0.985 | 13.42 / 0.930 |
| buffer 32 KiB | 336 | 9.23 / 1.002 | 12.26 / 1.008 | 16.98 / 0.996 |
| buffer 16 KiB | 336 | 9.04 / 1.041 | 12.18 / 1.042 | 16.34 / 0.992 |
| mark at every refill | 337 | 8.20 / 0.988 | 11.18 / 0.998 | 16.61 / 0.985 |
| no MADV_HUGEPAGE on regions | 336 | 9.42 / 1.010 | 12.62 / 0.995 | 17.24 / 1.000 |
| no MADV_HUGEPAGE at all | 336 | 9.64 / 0.997 | 12.87 / 1.021 | 17.65 / 1.045 |
| 256 KiB thread stacks | 336 | 9.46 / 0.986 | 12.75 / 1.012 | 17.96 / 0.982 |
| mark + BLOCK 256 | 337 | 7.89 / 0.997 | 9.61 / 0.952 | 12.62 / 0.905 |
| **mark + BLOCK 256 + 32 KiB (candidate)** | 337 | **7.73 / 0.969** | **8.93 / 0.901** | **12.17 / 0.871** |
| BLOCK 256 + 32 KiB, no mark | 336 | 8.91 / 1.049 | 10.95 / 1.002 | 13.41 / 0.938 |

Second batch (9 runs, `screen2-*`), all with mark at every refill: BLOCK 128 + 32 KiB 7.75 / 0.977 and
9.23 / 0.923; BLOCK 128 + 16 KiB 7.54 / 0.969 and 9.30 / 0.954; BLOCK 256 + 16 KiB 7.70 / 1.018 and
8.76 / 0.931; BLOCK 512 + 32 KiB 7.82 / 1.002 and 9.68 / 1.005 (8 / 12 threads). BLOCK 256 + 32 KiB
(7.75 / 0.974, 8.90 / 0.925) is the best combination at 12 threads and as good as any at 8; the smaller
blocks and buffers do not lower M further once the backlog is bounded.

Not kept:

* Smaller blocks or buffers alone lower M too little to pay for their T at 8 threads; marking at every
  refill is what bounds the backlog, and together the three changes are both lower in M and not slower.
* No MADV_HUGEPAGE and smaller stacks: no M gain (see the breakdown).
* `cand-spin`: workers out of chunks keep marking until every worker has sent its last block (instead
  of waiting at the barrier). Same M (7.73 / 9.07 / 12.12), wall 0.984 / 1.003 / 1.163 against the
  candidate in the same batch: the final-stage peak is not a backlog of idle owners.
* `cand-arena1` = candidate + `mallopt(M_ARENA_MAX, 1)` (+2 lines): one malloc arena instead of one per
  worker. Est. M 7.21-7.30 / 8.39-8.43 / 9.95 MB (-0.45 / -0.5 / -2.1 MB against the candidate). Wall
  against the candidate at 8 threads over three 21-run batches: +4.0%, +2.1% and -0.8% (break-even
  +1.9%, as 7.3 MB is at the cap); at 12 threads -0.2% (21 runs, break-even +2.1%); in the 9-run
  screen +1.4% / +0.1% / -0.3% at 8 / 12 / 20 threads (break-even at 20 threads about +7.8%). Borderline at 8 threads, and a single arena lock is the kind of shared state the
  board has penalised more than the sandbox (PR #8), so it is left for a separate board trial on top of
  this one. `M_ARENA_MAX` 2: similar M (7.24 / 8.34 / 10.26), wall 1.018 / 1.043 / 0.986 against the
  candidate. `M_TOP_PAD` 0: less M gain and slower (7.53 / 8.57 / 11.72 MB, wall 1.032 / 1.058 / 1.074).

## Final measurements (sandbox, not board results)

`reports/final-t8.json`: 31 interleaved runs, `base-c` against `cm-final` (the committed source, no
override, 8 threads): wall 49.2 -> 50.2 ms (median paired ratio 1.023, 9 of 31 pairs faster), est. M
9.28 -> 7.75 MB (-16.5%). Break-even (9.28/7.75)^0.4 x (336/337)^0.3 = 1.074: passes. The earlier
batches at 8 threads measured the same source 0.969, 0.974 and 0.978 against `cm-base`, so the local
time is neutral within noise.

`reports/final-t12.json` / `final-t20.json`: 21 runs each, `cm-base` against the candidate with the
override (`variants/mark-blk256-buf32.rs`, identical apart from the `SD_THREADS` line and one comment):
12 threads 55.5 -> 51.2 ms (0.917, 21 of 21 faster), est. M 12.69 -> 8.88 MB (-30%), break-even 1.152;
20 threads 64.5 -> 56.5 ms (0.866, 21 of 21), est. M 17.64 -> 11.99 MB (-32%), break-even 1.166. Above 8
threads the sandbox is oversubscribed, so these times only indicate that fewer queued blocks do not
hurt.

Expected on the board (not measured): if board M (11.4 MB) falls by the 8- to 12-thread local share
(-16.5% to -30%), M becomes about 8.0-9.5 MB, which is +3.6% to +7.3% K at equal T (M^0.2) minus 0.05%
for S. C board time varies about +-5% per run, so two board runs are advisable before deciding.

Board plan. The board runs 12 threads (the harness pins timed runs to `--cpuset-cpus=0-11`), so the
12-thread row is the one to compare with. The known unknown is synchronisation, not memory: with
256-event blocks a producer takes another owner's inbox lock 4 times as often as with 1024 (one locked
push per 256 events), and each worker now takes its own inbox lock at every 32 KiB refill (about twice
per 64 KiB of input instead of once per chunk). Locally that measured 0.97 to 1.02 paired at 8 threads,
but PR #8 showed the board charging cross-core traffic far more than the sandbox. So:

1. Run the board twice on this branch. Keep it if both runs' K beat the baseline's range, using the
   12-thread break-even T1/T0 of about 1.15 (about 1.07 with the 8-thread M ratio) as the T limit.
2. If T regresses past that, try BLOCK 512 with the same 32 KiB buffer and mark at every refill (half
   the pushes; screened at 7.82 / 9.68 MB est. M and 1.002 / 1.005 paired T at 8 / 12 threads, second
   batch above), before dropping the change.

## Correctness

* Full seed 1: `d8088b1c...` for the committed build and for the override copy at 1, 2, 3, 5, 8, 12, 17
  and 20 threads, and on every measured run (memrun checks each output).
* `smallcheck.py` (tiny and sample seeds 2 and 7 against the official reference): committed build, and
  the override copy at 1, 3, 5 and 8 threads.
* `fixtures.py` (new): official reference `c_join.py` against the override copy at 1, 3, 5, 8, 12 and 20
  threads on tiny and sample seed 42 and on hand-made files: names up to 70 KB with `""` escapes, 15-100
  KB records with quoted LFs (more than the 32 KiB buffer, so it doubles), a BOM header, 40k small
  records, and both kinds with no line end after the last record. All 36 cases match.
* Forced restarts: candidate with `bits = 8` (tables start 512 times too small and double until they
  fit) gives the full hash at 1-20 threads and passes smallcheck at 1, 5, 8 and 17 threads, as does the
  baseline. Note: with `bits = 6` both the baseline and the candidate give wrong, varying output at 17
  and 18 threads. There an owner gets m = 2^6/n + 1 <= 8 slots, so `used + 1 >= m` (skip events) is
  reached before `used > m / 8 * 7` (restart flag) and events are dropped without a restart. It only
  happens for m <= 8, which the real start (2^17 slots, m >= 8,193 for n <= 16) cannot reach; not
  changed here.

## Files

* `baseline.rs`: speed-demon `track-c/src/main.rs` at `f828bd8`. `candidate.rs`: the committed source.
* `make-variants.py`: writes `variants/*.rs` and `profile.rs` (the instrumented baseline);
  `variants/` is not committed (regenerate it). `build.sh SRC NAME`: native release build into
  `/projects/sandbox/.data/bin/NAME`.
* `fixtures.py BIN [--threads T]`: reference comparison on the fixtures above.
* `compare.py REPORT...`: tables in `reports/summary.md`. `reports/*.json`: memrun reports
  (`screen*` per thread count, `arena*` arena-max batches, `final-*`). `reports/cm-profile*.txt`: profile
  output.

## Overlap with other branches

`c-trim` (line trims) edits the same worker code of `track-c/src/main.rs`. The branches are separate board trials off `f828bd8` and are not rebased onto each other here. Whichever lands after the other must be rebased, rebuilt, re-hashed (full seed 1, `smallcheck`, `fixtures.py`) and re-counted: S 337 here is relative to the untrimmed base.
