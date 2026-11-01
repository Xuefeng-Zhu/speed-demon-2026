# Track B: PR #20's pure memory savings only (local sandbox measurements, not official scores)

**Board run pending.** All numbers here come from the 8 vCPU sandbox (Xeon Platinum 8488C, Linux 6.1, glibc 2.34, rustc 1.92.0, `RUSTFLAGS='-Ctarget-cpu=x86-64-v3'`, no PGO). None of them are board results.

PR #20 (`1802d16`) lowered board M from 73.8 to 56.6 MB, but board T rose from 0.172 s to 0.214 s, above the about 191 ms the keep rule allowed. This branch is the split the user asked for: keep only the savings that need no allocator setting and no change to the chunking, and drop `mallopt`. It is `experiments/b-mem2/pure-savings.rs` of branch `b-mem2` (SHA-256 `0090e1af...47ad`) as `track-b/src/main.rs`, on `speed-demon` `f828bd8` (baseline source SHA-256 `d3920254...66b9`). `pure-savings.patch` is the diff. `Cargo.toml`, `Cargo.lock` and `Dockerfile` are unchanged.

## Changes (from PR #20, as they were there)

1. **Early drops.** `qtext` and the sample-scan temporaries are dropped once the anchors are chosen, before the rows are allocated.
2. **Counting sort without the `end` copy.** `offs` has nl + 2 slots and is shifted in place; a second pass drops a term's repeats within a document (ids within a list only increase, so equal neighbours are the repeats).
3. **Late drops.** `plan.keys`, `filter`, `aoff`, `anchors` and `flat` (about 4 MiB) are released once the scan is done.
4. **u32 query offsets.** `qs` holds `(u8, u32)`, 400 KB less.

Not taken: the `mallopt` call, the rounds of shrinking chunks, and `b-mem2`'s 32 MiB stream capacity. The chunk cut and the syscall profile are the baseline's (74 / 42 / 215 `mmap` / `munmap` / `mprotect` at 12 threads against 92 / 48 / 138, `experiments/b-mem2/reports/syscalls.txt` on branch `b-mem2`).

## Measurements

The binary built here (`53df5557...`) is byte-identical to `b2-cand`, the pure-savings binary measured on branch `b-mem2`. Fresh runs at the board's 12 threads (the harness pins timed runs to `--cpuset-cpus=0-11`); tools are `experiments/b-mem2/tools/{memrun,pairs}.py` on branch `b-mem2`:

| 12 threads | baseline | b-pure |
| --- | ---: | ---: |
| est. M, sampled peak RssAnon + RssShmem + 1.46 MB output (median of 11, `reports/mem-t12.json`) | 66.93 MB | 59.50 MB (-11.1%) |
| wall, median of 11 memrun runs | 229.7 ms | 220.0 ms |
| paired wall, 21 rounds (`reports/time-t12.json`) | | -4.31% (15/21), CPU -4.55% |
| minor faults | 25,045 | 21,350 |
| S (code + Dockerfile) | 557 + 26 = 583 | 560 + 26 = 586 |

On `b-mem2` the same binary gave 54.39 MB at 8 threads and 52.58 MB at 6 (baseline 62.40 and 61.48), and paired wall -4.46% and -6.52%. Freed stream buffers stay resident in the glibc arenas (the first freed mapped stream raises the dynamic mmap threshold), which is why these savings keep less than PR #20 did; the peak is at the end of the index phase.

## Keep rule

T1/T0 < (M0/M1)^0.4 x (S0/S1)^0.3, M capped at 44 MB (not binding here).

| M basis | M0 to M1 | break-even T1/T0 | break-even board T | K at equal T |
| --- | --- | ---: | ---: | ---: |
| local est. M, 12 threads | 66.93 to 59.50 | 1.047 | 180 ms | +2.3% |
| board baseline 73.8 with the baseline's 6.6 MB offset added to 59.50 | 73.8 to 66.1 | 1.043 | 179 ms | +2.1% |

Locally T falls by about 4%, so the change passes with room here. It passes on the board if T stays below about 179 ms (baseline 172 ms).

## What the board run decides

- If board T stays below about 179 ms, the counting sort and the drops are confirmed as savings, and `b-mem2` (the same plus a 32 MiB stream capacity, 49.4 MB est. M) is the next trial: it tests whether PR #20's T came from its shrinking rounds or from its syscalls.
- If board T rises like PR #20's even here, the cost is in these four changes, not in `mallopt` or the rounds, and the branch is reverted.

## Correctness

- Full seed 1 `f86973c2...0927` at `SD_THREADS` 1, 12 and the default thread count, and in every measured run.
- `smallcheck.py b` (tiny and sample seeds 2 and 7 against the official reference) at the default thread count, 1 and 12.
- `experiments/b-filter-parse/check_all.sh`: pass=34 fail=0 xfail=2 at the default thread count, 1 and 12 (the two xfails are the baseline's no-trailing-LF fixtures, outside spec 2.1).

## Overlap with other branches

`b-trim` and `b-mem2` edit the same functions in `track-b/src/main.rs`. Whichever lands after another must be rebased, re-hashed and re-counted: the S figures here are relative to the untrimmed `f828bd8`.
