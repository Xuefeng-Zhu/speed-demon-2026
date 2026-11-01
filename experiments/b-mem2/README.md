# Track B: lower peak memory without mallopt (retry of PR #20; local sandbox measurements, not official scores)

PR #20 (`1802d16`, branch `b-mem`, folder `experiments/b-mem/` there) lowered board M from 73.8 MB to 56.6 MB but board T rose from 0.172 s to 0.214 s, more than the about 191 ms the keep rule allowed for that M. Two parts of it were suspected of costing T on the board: the fixed 128 KiB mmap threshold (`mallopt(M_MMAP_THRESHOLD, 128 KiB)`, many `mmap`/`munmap` calls contending on the mm lock, the same class of problem as Track A PR #19) and the rounds of shrinking chunks (tail idle time). This candidate keeps only the parts that save memory without touching the allocator settings or the chunking, and replaces the fixed threshold with one buffer-size choice that has the same effect on the one buffer that matters.

`baseline.rs` is `track-b/src/main.rs` at `speed-demon` `f828bd8` (the `b7c4ae5` source of board run `run-2802b79df46d`: T=0.172 s, M=73.8 MB, S=583, K=27.00), SHA-256 `d39202542d59ccededa7fd0b7bbbd3c703d63f5dd98a80e02dd97f2acaff66b9`, byte-identical to `experiments/b-mem/baseline.rs`. `candidate.rs` is the committed `track-b/src/main.rs` of branch `b-mem2`, SHA-256 `b4adf48d085e2b1e76a14ae3f72a527180944510c853263e7b70dd38015557ce`. Its last edits are comments only: the measured binary `6222c4fc...` was built from the first commit's source (`5f5ba96b...`), and the follow-up comment on the glibc threshold shifts line numbers in panic locations, so the current source builds to `0a8b1cf7...` (99 bytes differ, no code change; it passes the full hash at 1, 12 and the default thread count and `smallcheck.py`). `pure-savings.rs` (SHA-256 `0090e1af...`) is the intermediate step without the stream change. `Cargo.toml`, `Cargo.lock` and `Dockerfile` are unchanged; std only; no new libc function.

All numbers below are local sandbox measurements, not official scores and not board results. Board run pending.

## Summary

| | baseline (`f828bd8`) | PR #20 (`1802d16`) | pure savings | **candidate** |
| --- | ---: | ---: | ---: | ---: |
| `mallopt` | no | yes | no | **no** |
| Chunking | `nthreads * m` equal | rounds 7:3 | equal (unchanged) | **equal (unchanged)** |
| S (code + Dockerfile) | 557 + 26 = 583 | 564 + 26 = 590 | 560 + 26 = 586 | **560 + 26 = 586** |
| est. M, 12 threads (median of 11) | 67.22 MB | 48.48 MB | 59.50 MB | **49.36 MB (-26.6%)** |
| est. M, 8 threads | 62.40 MB | 46.51 MB | 54.39 MB | **48.56 MB (-22.2%)** |
| est. M, 6 threads | 61.48 MB | 48.74 MB | 52.58 MB | **50.90 MB (-17.2%)** |
| Paired wall vs baseline, 21 pairs, 12 / 8 / 6 threads | | -4.39% / -4.54% / -10.42% | -5.45% / -4.46% / -6.52% | **-4.18% / -4.57% / -3.31%** |
| `mmap` / `munmap` / `mprotect` calls, 12 threads | 92 / 48 / 138 | 151 / 70 / 366 | 74 / 42 / 215 | 100 / 73 / 434 |
| Minor faults, 12 threads (median of 21) | 25,015 | 24,708 | 21,275 | 24,853 |

est. M is the tool's estimate of the board's cgroup peak: sampled peak of RssAnon + RssShmem plus the 1.46 MB `results.txt` on tmpfs (`tools/memrun.py`). Board M for the baseline is 6.6 MB above this estimate and for PR #20 8.1 MB above it.

## Environment

| Item | Value |
| --- | --- |
| CPU | Intel Xeon Platinum 8488C, 8 vCPUs (4 cores x 2 SMT), shared host; the board is an i5-13500, 6 P-cores / 12 threads |
| Kernel, libc | 6.1, glibc 2.34 (official image: Debian 13, glibc 2.41; the malloc behaviour used here is the same) |
| Compiler | rustc 1.92.0, `RUSTFLAGS='-Ctarget-cpu=x86-64-v3' cargo build --release`, no PGO (the Dockerfile builds with PGO) |
| Data | full seed 1 (`docs.txt` 253,827,587 B, `queries.txt` 1,763,534 B) |
| Binaries | baseline `aef038dd...` (same as `bin/base-b7c4` of `experiments/b-mem`), PR #20 `6d1ee070...` (same bytes as the binary measured in `experiments/b-mem`), pure savings `53df5557...`, candidate `6222c4fc...` |
| Tools | `strace` and `perf` are not installed; `tools/sysc.c` counts syscalls with ptrace |

## Changes

From PR #20, kept as they were there (`variants/pure-savings.patch`):

1. **Early drops.** `qtext` and the sample-scan temporaries (`freq`, `bools`, `order`, `new`, the renumbered frequencies, renamed `df` so one `drop` covers both) are dropped once the anchors are chosen, before the rows are allocated. +1 S line.
2. **Counting sort without the `end` copy.** `offs` has nl + 2 slots: `offs[l + 2]` counts list l, after the prefix sum `offs[l + 1]` is where list l's next id goes, and after the fill `offs[l]` is the start of list l. A second pass drops a term's repeats within a document (equal neighbours in its sorted list) and closes the gaps. No 212 KB clone of `offs` per chunk, and a faster sort. +1 S line.
3. **Late drops.** `plan.keys`, `filter`, `aoff`, `anchors` and `flat` (about 4 MiB) are replaced by empty vectors once the scan is done. +1 S line.
4. **u32 query offsets.** `qs` holds `(u8, u32)` instead of `(u8, usize)`, 400 KB less. 0 S lines.

Not taken from PR #20: the `mallopt` call and the rounds of shrinking chunks. The chunk cut is byte-identical to the baseline's.

New (`variants/big-stream-on-pure.patch`):

5. **A 32 MiB stream capacity.** Each chunk's token stream is created with `Vec::with_capacity(1 << 24)` (32 MiB of address space) instead of `(hi - lo) / 16` elements. 32 MiB is glibc's `DEFAULT_MMAP_THRESHOLD_MAX` on 64-bit and the block with its header is above it, so it is served by its own `mmap` whatever the dynamic threshold has become. This depends on that glibc constant, and the code comment says so: a libc or base image with a higher maximum would bring the arena retention back, and the fallback is `pure-savings.rs` (unless an arena already holds 32 MiB of free memory, which never happens here), and freeing it never raises the threshold (glibc only raises it for freed mapped blocks of at most that size). Only the written pages are resident, about 0.09 bytes per corpus byte as before, and they go back to the OS with the `munmap` when the chunk is done. A chunk is at most 16 MiB of corpus plus the cut to a 64-document line, and every stream entry needs at least two corpus bytes, so the capacity is never exceeded (if it were, the `Vec` would just grow). 0 S lines (comments only).

### Why the pure savings alone keep less than PR #20

Without the fixed threshold, the first stream buffer that is freed raises glibc's mmap threshold to its own size (about 1.3 MiB at 12 threads), so later streams come from the threads' arenas and their pages stay resident after `free` (`experiments/b-mem/README.md`, "Why freed memory stays resident"). The sampled series (`reports/series.txt`) show the pure-savings peak at the end of the index phase (194 ms of 229 ms at 12 threads), when all chunk lists, the bitmap rows and the retained stream memory are resident at once: 56.7 MB vs 46.0 MB for PR #20. The pure savings are real (-7.7 MB at 12 threads, -8.0 MB at 8), but the retained streams eat most of what PR #20 got from the threshold. The FEAT-002 lesson for Track D (peak 52 to 68 MB without its `mallopt`) is the same effect.

### Variants against the pure savings

memrun, 11 interleaved runs each (`reports/mem2-t*.json`, `reports/mem-final-t*.json`):

| Variant | Patch | est. M 12 threads | est. M 8 threads | S |
| --- | --- | ---: | ---: | ---: |
| pure savings | `variants/pure-savings.patch` | 59.50 MB | 54.40 MB | 586 |
| + one stream buffer per thread, reused across chunks | `variants/reuse-stream-on-pure.patch` | 56.80 MB | 51.76 MB | 587 |
| + `malloc_trim(0)` once after the index | `variants/trim-after-index-on-pure.patch` | 59.50 MB | 54.47 MB | 587 |
| + both | `variants/reuse-trim-on-pure.patch` | 56.67 MB | 51.70 MB | 588 |
| **+ 32 MiB stream capacity (candidate)** | `variants/big-stream-on-pure.patch` | **49.36 MB** | **48.56 MB** | 586 |
| PR #20 without `mallopt` (`experiments/b-mem/variants/loo-no-mallopt.patch`, rounds kept) | | 53.67 MB | 52.52 MB | 588 |

- `malloc_trim(0)` after the index does nothing for the peak: the peak is at the end of the index, before the trim, as `experiments/b-mem` found for its own trim variant.
- Reusing one stream per thread removes the retention but keeps every thread's touched stream pages resident until the thread ends, and the index ends with all of them live next to all lists (52.9 MB sampled peak at 12 threads).
- The 32 MiB capacity gets the effect of PR #20's fixed threshold on the stream buffers only, and is 4.3 MB below PR #20 without `mallopt` with equal chunks.

## mmap/munmap counts and the mm-lock hypothesis

`tools/sysc.c` runs the binary under ptrace and counts syscall entries of all threads (timing under ptrace is meaningless; counts only). 3 runs per binary (`reports/syscalls.txt`), medians:

| Binary | Threads | mmap | munmap | mprotect | madvise | total syscalls |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| baseline | 12 | 92 | 48 | 138 | 289 | 960 |
| PR #20 | 12 | 151 | 70 | 366 | 299 | 1,280 |
| PR #20 without `mallopt` | 12 | 86 | 55 | 145 | 288 | 967 |
| pure savings | 12 | 74 | 42 | 215 | 289 | 1,007 |
| candidate | 12 | 100 | 73 | 434 | 289 | 1,286 |
| baseline | 8 | 76 | 35 | 139 | 273 | 817 |
| PR #20 | 8 | 111 | 53 | 408 | 280 | 1,144 |
| pure savings | 8 | 68 | 43 | 156 | 273 | 830 |
| candidate | 8 | 74 | 52 | 439 | 273 | 1,128 |

Minor faults (`os.wait4`, median of 21 runs, `reports/time-t*.json`) are 24,000 to 25,000 for the baseline, PR #20 and the candidate at 8 and 12 threads.

PR #20 makes about 60 more `mmap`, 22 more `munmap` and 230 more `mprotect` calls than the baseline at 12 threads, over a run of about 200 ms, and the same number of page faults. That is a few hundred extra mm-lock acquisitions and about 22 extra TLB shootdowns (only `munmap` of touched pages needs one; `mprotect` here extends arena heaps over pages never touched). At a few microseconds each that is well under 1 ms of the 42 ms by which the board's T rose, so these counts do not support the mm-lock explanation; on this host PR #20 is as fast as the baseline or faster at 6, 8 and 12 threads. The candidate's syscall profile is close to PR #20's (the extra `mprotect` calls come from arena heaps that grow instead of reusing freed streams). If the board slowdown did come from these calls, the candidate would carry it too; `pure-savings.rs` has the baseline's syscall profile and is the fallback (see Decision).

The remaining PR #20 suspects that the candidate does not have are the rounds of shrinking chunks: 1.4 times larger first-round chunks (whose `docs` arrays exceed L2 on this host, `experiments/b-mem/reports/csr-cost.txt`) and the 30% second round. With 12 threads in step on the box, the second round adds a phase in which every thread waits for the slowest small chunk.

## Paired wall times

1 warmup plus 21 rounds; each round runs every binary once in rotated order, hash asserted on every run (`tools/pairs.py`, no memory sampler running; `reports/time-t*.json`). Delta = median of per-round ratios to the baseline; faster = rounds where the binary beat the baseline.

| Threads | baseline ms | PR #20 | pure savings | candidate |
| ---: | ---: | ---: | ---: | ---: |
| 12 (oversubscribed) | 222.9 | 214.3, -4.39% (19/21) | 210.3, -5.45% (21/21) | **215.8, -4.18% (19/21)** |
| 8 | 210.1 | 200.8, -4.54% (20/21) | 200.8, -4.46% (21/21) | **202.1, -4.57% (20/21)** |
| 6 | 250.0 | 221.4, -10.42% (21/21) | 234.9, -6.52% (18/21) | **241.1, -3.31% (16/21)** |

Paired CPU at 12 / 8 / 6 threads: candidate -4.48% / -4.15% / -2.41%, pure savings -4.97% / -3.62% / -4.86%. The gain is the counting sort without `end`. At 6 threads PR #20's rounds shorten the 18-chunk tail, which the candidate (equal chunks, as the baseline) does not have; the board runs 12 threads. Locally PR #20 was also faster than the baseline, while on the board it was 24% slower, so these local times do not predict the board's T well.

## Keep rule

T₁/T₀ < (M₀/M₁)^0.4 × (S₀/S₁)^0.3, M capped at 44 MB (Mref/50).

| | M₀ → M₁ | (M₀/M₁)^0.4 | (S₀/S₁)^0.3 | break-even T₁/T₀ | break-even board T | K factor at equal T |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| candidate, local est. M ratio at 12 threads | 67.22 → 49.36 | 1.1315 | 0.9985 (583 → 586) | 1.130 | 194 ms | 1.063 |
| candidate, board M via PR #20's offset (49.36 + 8.1 = 57.5 MB) | 73.8 → 57.5 | 1.1050 | 0.9985 | 1.103 | 190 ms | 1.050 |
| candidate, local 8 threads | 62.40 → 48.56 | 1.1055 | 0.9985 | 1.104 | 190 ms | 1.050 |
| pure savings, 12 threads | 67.22 → 59.50 | 1.0500 | 0.9985 | 1.048 | 180 ms | 1.024 |

M stays above the 44 MB cap, so the cap does not bind. Locally T₁/T₀ is 0.958 (12 threads) and 0.954 (8 threads), so the candidate passes with a wide margin here; on the board it passes if T stays below about 190 ms. Predicted K: about +5% to +6% at equal T (K about 28.4 to 28.7 from 27.00), +8.6% if the local -4.2% carried over. This is an estimate from local measurements, not a board result.

## Decision

The user's split for this retry was "only the pure savings, no `mallopt`". The 32 MiB stream capacity goes beyond that: it is an allocator-dependent change of the same family, and it brings back a syscall profile close to PR #20's (100 / 73 / 434 `mmap` / `munmap` / `mprotect` against PR #20's 151 / 70 / 366). So there are two trials, in this order:

1. **Branch `b-pure` first** (`pure-savings.rs` as `track-b/src/main.rs`, on `speed-demon`, folder `experiments/b-pure/`): the split the user asked for. Baseline syscall profile, equal chunks, no allocator change; break-even about 180 ms, about +2.4% K at equal T. If its board T holds, the counting sort and the drops are confirmed on the board.
2. **Branch `b-mem2` second.** It deliberately tests "rounds vs syscalls": it differs from PR #20 mainly by not having the shrinking rounds, and keeps a PR #20-like syscall count. If board T stays below about 190 ms, the rounds were PR #20's cost and the stream trick is kept. If board T rises again like PR #20's, the syscalls (or the stream mappings) are the cost, and `b-pure` is the version to keep.

Risk noted, not measured: if the board had THP set to `always`, the 32 MiB stream mappings could get 2 MiB pages, rounding each stream's resident size up to a multiple of 2 MiB (at most about 1 MB more per live stream). The sandbox has THP `madvise`.

## Correctness

- Full seed 1: every warmup and measured run in every report produced `f86973c210228141bcb6f1f1b10188ad2a9b65f71e7cd7cf4590b38de4e80927` (asserted by `tools/memrun.py`, `tools/pairs.py` and the `sysc` runs), and so did the candidate at `SD_THREADS` = 1, 2, 3, 5, 6, 7, 8, 9, 12, 16 and 24.
- `experiments/b-filter-parse/check_all.sh` (tiny seeds 1 to 20, sample seeds 2, 3, 4, 5, 7 and the `make_edge.py` fixtures, byte for byte against `official/reference/b_index.py`): pass=34 fail=0 xfail=2 at the default thread count, at 1 and at 12 threads, the same as the baseline. The xfails are the pre-existing `edge/no_lf` and `edge/no_lf_docs` (`docs.txt` without a trailing LF, outside spec 2.1).
- `tools/smallcheck.py b` (tiny and sample seeds 2 and 7): ok at the default thread count, 1 and 12.
- `cargo build --release` with `-Ctarget-cpu=x86-64-v3` compiles without warnings. `grep mallopt track-b/src/main.rs` finds nothing.

## Files

| File | Content |
| --- | --- |
| `baseline.rs`, `candidate.rs`, `pure-savings.rs` | sources (SHA-256 above) |
| `variants/pure-savings.patch` | baseline to pure savings (changes 1 to 4) |
| `variants/big-stream-on-pure.patch` | pure savings to candidate (change 5) |
| `variants/reuse-stream-on-pure.patch`, `trim-after-index-on-pure.patch`, `reuse-trim-on-pure.patch` | rejected variants against `pure-savings.rs` |
| `reports/mem1-t*.json`, `mem2-t*.json`, `mem-final-t*.json` | `tools/memrun.py` reports (binary names: `base-b` baseline, `b-mem` PR #20, `b-mem-nomallopt` PR #20 without `mallopt`, `b2-cand` pure savings, `b2-reuse`, `b2-trim`, `b2-reuse-trim` variants, `b2-final` candidate) |
| `reports/time-t*.json` | `tools/pairs.py` reports, 21 rounds at 12, 8 and 6 threads |
| `reports/syscalls.txt`, `reports/series.txt` | `tools/sysc` counts, `tools/series.py` RSS series (one run each) |
| `tools/` | `memrun.py`, `sloc.py`, `smallcheck.py` (shared round-4 tools), `pairs.py`, `series.py`, `faults.py`, `sysc.c`, `build.sh`; paths assume `/projects/sandbox/.data` |

## Reproduce

```sh
D=/projects/sandbox/.data; E=experiments/b-mem2; T=$E/tools
mkdir -p $D/b2/bb && cp -r track-b/Cargo.toml track-b/Cargo.lock track-b/.cargo track-b/src $D/b2/bb/
$T/build.sh $E/baseline.rs base-b; $T/build.sh $E/pure-savings.rs b2-cand; $T/build.sh $E/candidate.rs b2-final
git show 1802d16:track-b/src/main.rs > $D/b2/b-mem.rs && $T/build.sh $D/b2/b-mem.rs b-mem
gcc -O2 -o $D/b2/sysc $T/sysc.c
for t in "" 1 12; do sh experiments/b-filter-parse/check_all.sh $D/bin/b2-final $t; done
for t in 12 8 6; do python3 $T/memrun.py --track b --runs 11 --threads $t base-b b-mem b2-cand b2-final; done
for t in 12 8 6; do python3 $T/pairs.py --threads $t --runs 21 base-b b2-final b-mem b2-cand; done
SD_THREADS=12 SD_DATA=$D/b-full SD_OUT=/dev/shm/o $D/b2/sysc $D/bin/b2-final
python3 $T/series.py b2-final 12
python3 $T/sloc.py $E/candidate.rs
```

## Overlap with other branches

`b-trim` (line trims) and `b-pure` edit the same functions of `track-b/src/main.rs`. The branches are separate board trials off `f828bd8` and are not rebased onto each other here. Whichever lands after another must be rebased, rebuilt, re-hashed (full seed 1 and `check_all.sh`) and re-counted: S 586 here is relative to the untrimmed base.
