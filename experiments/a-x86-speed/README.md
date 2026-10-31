# Track A x86 speed work: paired benchmark harness and A/A noise

Local x86 VM measurements only. These are not official scores and were not taken on the scoring
box (i5-13500, 12 threads). They exist so that every Track A change on branch `a-x86-speed` is
measured the same way against the immediately prior source.

## Host

Shared KVM VM, Intel Xeon Platinum 8488C, 8 vCPUs (4 cores x 2 HT), AVX2, kernel 6.1,
rustc 1.92, python 3.11. Input is the full seed-1 dataset (238,836,234 bytes) generated to the
gitignored `.data/a-full` and kept in page cache. Outputs go to gitignored `.out/`.

```sh
python3 official/generators/a_ingest.py --seed 1 --scale full --out .data/a-full
```

## Tools

- `bench.py`: builds each `--variant NAME=PATH.rs` (first one is the baseline) with
  `rustc --edition 2021 -C opt-level=3 -C codegen-units=1 -C lto=fat -C panic=abort -C target-cpu=x86-64-v3`
  into the gitignored `target/`, records source and binary SHA-256, then per thread count runs
  `--warmup` discarded rounds and `--runs` measured rounds. Each round runs every variant once in
  a freshly shuffled order from a seeded RNG (seed stored in the report). Before each run the old
  `summary.txt` is removed; wall time is `time.perf_counter` around the child, utime, stime and
  maxrss come from `os.wait4`, and every output SHA-256 must equal the published full seed-1 hash
  `495ca096...1cd3`. The JSON report has every sample plus median, min, mean of the middle 60%,
  a board-style statistic (mean of the middle 3 of each consecutive block of 5 runs, averaged),
  and per-round paired ratios candidate/baseline with their median and win fraction.
- `check.py BINARY`: full correctness suite. Full seed-1 hash at `SD_THREADS` 1, 2, 3, 6, 8, 12
  and unset, `track-a-verification/test.py --io directories`, `page_end_test.py` against the
  official reference, `latency_grid_test.py`, and sample seeds 2, 98, 999, 4242 byte-compared
  with the official reference output (generated under `.data/` if missing). Exits non-zero on
  any failure.
- `baseline.rs`: exact copy of `track-a/src/main.rs` at the branch point (`speed-demon`).

```sh
python3 experiments/a-x86-speed/check.py track-a/target/release/solution
python3 experiments/a-x86-speed/bench.py --variant base=experiments/a-x86-speed/baseline.rs \
  --variant cand=experiments/a-x86-speed/<candidate>.rs --threads 8,12 --runs 41 --report <out>.json
```

The production build at the branch point passed `check.py` (all 14 checks).

## A/A noise

`baseline.rs` against itself under two names, 3 warmup rounds and 41 measured rounds per thread
count, in two independent invocations (shuffle seeds 1 and 2). All 352 outputs hashed correctly.

| Report | Threads | base median (s) | base2 median (s) | paired ratio median | base2 win fraction |
|---|---:|---:|---:|---:|---:|
| `aa-noise.json` | 8 | 0.0378 | 0.0381 | 1.0114 | 44% |
| `aa-noise.json` | 12 | 0.0465 | 0.0459 | 0.9874 | 66% |
| `aa-noise-2.json` | 8 | 0.0376 | 0.0374 | 1.0015 | 49% |
| `aa-noise-2.json` | 12 | 0.0465 | 0.0463 | 1.0061 | 44% |

Single-round paired ratios are wide (in `aa-noise.json` the 10th to 90th percentile is about
0.90 to 1.08 at 8 threads and 0.93 to 1.05 at 12), but the paired median over 41 rounds stayed
within 0.987 to 1.011. The A/A noise band for the paired median is therefore taken as
plus or minus 1.5%.

12 threads oversubscribes this 8 vCPU host (about 23% slower than 8), so it only approximates the
scoring box thread count; it is used as a regression guard rather than a target.

## Decision rule for later changes

Keep a change only if all of the following hold, measured against the immediately prior source:

1. `check.py` passes for a binary built from the candidate.
2. At 8 threads the paired median ratio candidate/baseline is below 0.985 (better than the
   A/A band) with at least 41 measured rounds.
3. At 12 threads the paired median ratio is at most 1.015 (no regression beyond noise).
4. Both conditions reproduce in a second independent `bench.py` invocation with a different
   shuffle seed.

Rejected candidates are archived under their own `experiments/a-<name>/` directory with the
variant source, baseline, JSON report and a README.
