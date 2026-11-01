# Track B: a small last round of chunks (index tail with threads of unequal speed)

Every number in this folder is a local sandbox measurement (Xeon Platinum 8488C KVM guest, 8 vCPUs = 4 cores x 2 SMT, siblings c and c + 4, kernel 6.1, glibc 2.34, rustc 1.92 / LLVM 21, x86-64-v3, no PGO, full seed 1), not an official score. The only official numbers are quoted from `track-b/PERF.md`: production PR #28 (`b-pure`, origin/speed-demon `d9d69e7`) ran T 173.0 to 175.5 ms, M 62.0 to 62.5 MB, S 586, K 27.67 to 27.86 in three board runs.

## Summary

**Change** (`candidate.rs`, 1 S line): at least two rounds of `nthreads` chunks instead of `max(1, m)` rounds of equal chunks, and the last round's byte ranges are a third as large as the others. In `main()`:

```rust
let nchunks = nthreads * data.len().div_ceil(nthreads << 24).max(2);   // was .max(1)
let cut = |k: usize| {
    let w = k + 2 * k.min(nchunks - nthreads);          // weight 3 per range, 1 in the last round
    let mut i = line_start(data, w * data.len() / (3 * nchunks - 2 * nthreads));
    ...                                                  // the 64-document alignment is unchanged
```

| Threads | Baseline chunks (size) | Candidate chunks (sizes) |
| ---: | --- | --- |
| 8 | 16 (15.9 MB) | 16 (8 x 23.8 MB, then 8 x 7.9 MB) |
| 12 | 24 (10.6 MB) | 24 (12 x 15.9 MB, then 12 x 5.3 MB) |
| 20 | 20 (12.7 MB, one per thread) | 40 (20 x 9.5 MB, then 20 x 3.2 MB) |

**Why.** At 20 threads the baseline has exactly one chunk per thread, so the slowest thread (an E-core on the i5-13500, if the box exposes them) ends the index phase while the others idle. The small last round goes to whichever threads finish first. As a side effect the streams of the last round, which are alive at the peak (end of the index), are a third as large, so max RSS drops 3 to 7 MB at every thread count.

**Final paired results** (41 pairs; candidate vs baseline binary; median of per-pair wall ratios with a 95% bootstrap interval; reports `reports/final-*.json`, `reports/final2-*.json`):

| Setting | Paired wall | Wins | CPU | Wall ms cand / base | Max RSS KiB cand / base |
| --- | --- | ---: | ---: | --- | --- |
| plain 8 threads (uniform) | -0.19% [-0.87, +1.30] | 22/41 | -0.18% | 189.3 / 188.5 | 52,324 / 55,660 |
| p20 emulation, 20 threads | **-8.26%** [-11.69, -3.95] | 31/41 | +4.01% | 306.0 / 330.9 | 65,016 / 71,240 |
| p12 emulation, 12 threads | **-2.87%** [-6.22, -0.33] | 28/41 | +1.45% | 337.7 / 342.3 | 54,464 / 60,068 |
| plain 12 threads (uniform, oversubscribed) | -0.51% [-2.02, +0.12] | 25/41 | +1.64% | 192.4 / 193.8 | 53,052 / 59,884 |
| m20 (milder 20-thread emulation), 21 pairs | -9.36% [-10.43, -1.83] | 16/21 | +4.48% | 368.1 / 407.2 | 65,116 / 71,276 |
| m12 (milder 12-thread emulation), 21 pairs | -0.93% [-4.14, +1.09] | 14/21 | +1.16% | 446.7 / 449.9 | 53,740 / 59,996 |
| u20 (20 threads, no pinning), 21 pairs | +0.67% [-1.76, +2.83] | 8/21 | +3.98% | 203.6 / 203.6 | 63,624 / 71,056 |
| s20 (20 threads, 2 spinners, no pinning), 21 pairs | +2.32% [+0.87, +4.05] | 3/21 | +3.87% | 260.6 / 256.4 | 63,708 / 70,916 |

**K estimate** (local deltas applied to the board's K 27.75, the mean of the three #28 runs; it assumes board M moves like local max RSS at the box's thread count, and S 586 -> 587):

| If the box runs like | T factor | M factor | K |
| --- | ---: | ---: | ---: |
| 20 threads with slow E-core threads (p20) | 1.044 | 1.019 | 29.5 (+6.3%) |
| 20 threads, milder (m20) | 1.050 | 1.018 | 29.7 (+6.9%) |
| 20 threads, all equal (u20) | 0.997 | 1.022 | 28.3 (+1.9%) |
| 12 threads, 6 fast + 6 slow (p12) | 1.015 | 1.020 | 28.7 (+3.4%) |
| 12 threads, all equal (plain 12) | 1.003 | 1.025 | 28.5 (+2.7%) |
| sandbox 8 threads | 1.001 | 1.012 | 28.1 (+1.3%) |

The S factor is 0.99974 (+1 line). Without the M gain the estimate is 27.7 to 29.1. Board noise is about +-5% per run, so a single board run cannot confirm a gain under about 5%.

**Risk at 12 threads.** At 12 threads the first-round chunks are 1.5 times the baseline's (15.9 vs 10.6 MB), similar to PR #20's 7:3 rounds (1.4 times). If the box runs 12 threads and #20's board slowdown came from its rounds rather than from `mallopt` (section 8), this candidate could repeat it there. `variants/h31x.patch` is the fallback: the same two rounds at 20 threads (m = 1), and chunks identical to the baseline when m >= 2 (8 and 12 threads). It keeps the 20-thread tail fix and the 20-thread M drop (-6 MB) and gives up the 12-thread M drop.

## 1. The heterogeneity emulation

The sandbox has 8 uniform vCPUs, so it cannot show an E-core tail directly. `tools/pin.c` is an `LD_PRELOAD` shim (test-only, never in the solution) that pins the i-th created thread to CPU `SD_EMU_CPUS[i % n]` through its pthread attributes. Track B's `par()` spawns its workers in order k = 0..n-1, once for the index and once for the answers, so worker k always runs on the listed CPU. The shim also holds each worker until all n of its batch exist. Without that start gate, the unpinned main thread shares a vCPU with running workers and the last workers started up to 90 ms late, which is an emulation artifact. Production binaries run unmodified.

`tools/emu.py` defines the layouts. "P" workers stand for P-core threads, "E" workers for E-core threads. A worker's speed is its share of a vCPU.

| Layout | Threads | Pinning | Spinners | Nominal E/P speed |
| --- | ---: | --- | --- | ---: |
| plain8 | 8 | none | none | 1 |
| plain12 | 12 | none | none | 1 |
| u20 | 20 | none | none | 1 |
| s20 | 20 | none | nice-0 on vCPUs 3 and 7 | (scheduler decides) |
| p20 | 20 | workers 0-11 two per vCPU on 0,1,2,4,5,6; workers 12-19 four per vCPU on 3,7 | none | 0.5 |
| m20 | 20 | as p20 | nice-2 on each P vCPU | 0.66 |
| p12 | 12 | workers 0-5 one per vCPU on 0,1,2,4,5,6; workers 6-11 three per vCPU on 3,7 | nice-3 on each P vCPU | 0.5 |
| m12 | 12 | as p12 | nice-0 on each P vCPU | 0.67 |

The E vCPUs 3 and 7 are the two siblings of core 3, so the P and E groups use whole cores and both see a busy SMT sibling.

**Validation with the baseline.** `tools/mkinst.py` makes an instrumented copy (per-chunk start and end, phase stamps, VmRSS and VmHWM at each chunk end, all printed at exit) in the format of `experiments/b-linux-profile/run.py`. The key metric is the share of vCPU time in the index window with no busy worker on that vCPU ("vCPU idle"). Thread idle (the run.py utilization) overstates the loss when threads share vCPUs. Baseline vs itself, 5 pairs (`reports/val-*.json`), and in the final 11-pair instrumented runs (`reports/tail-*.json`):

| Layout | Index ms | vCPU idle | Idle tail (last thread end - first) | Measured E/P chunk speed |
| --- | ---: | ---: | ---: | ---: |
| plain8 | 131 to 133 | 2.7 to 3.4% | 6 ms | |
| u20 | 144 | 4.1% | 56 ms (threads time-share, vCPUs stay busy) | |
| s20 | 193 | 3.3% | 84 ms | |
| p20 | 237 to 250 | 26.7 to 27.8% | 108 to 150 ms | 0.67 to 0.69 |
| m20 | 287 to 290 | 25.4 to 29.0% | 129 to 138 ms | 0.68 to 0.70 |
| p12 | 244 to 270 | 18.1 to 18.7% | 66 to 81 ms | 0.39 to 0.51 |
| m12 | 311 to 318 | 24.4 to 25.1% | 90 to 99 ms | 0.66 to 0.67 |

The pinned layouts reproduce the tail: with one chunk per thread at 20 threads, the P vCPUs finish their chunks after about 150 ms and idle while the E core works on until about 240 ms. The suggested unpinned spinner setup (s20) does not: the scheduler migrates threads off the loaded vCPUs, so vCPU idle stays at 3%. I kept it only as a check.

With the candidate (`reports/tail-*.json`, 11 instrumented pairs), p20's vCPU idle falls from 27.8% to 11.2% and its idle tail from 150 to 47 ms; m20 from 29.0% to 14.2% (138 to 49 ms); m12 from 25.1% to 19.1% (90 to 64 ms); p12 stays at 18.7% vs 20.5% (81 to 72 ms), because at 12 threads the E threads still take one large first-round chunk each; plain8 stays at 3%. The index phase changed by -8.1 ms (p20), -20.6 ms (m20), -17.3 ms (m12), -0.7 ms (p12) and +1.6 ms (plain8), and the answer phase by +6.2 ms at p20 and +7.8 ms at m20 (40 chunks instead of 20). The walls of these 11-pair instrumented runs are too noisy to read (p20 +0.84%, 5/11); the decision metric is the 41-pair production runs above.

Caveats of the emulation. A vCPU runs faster when fewer cores are busy (memory and L3 contention), so idle vCPUs cost less wall time than their share suggests: cutting p20's vCPU idle from 28% to 11% shortened the index by only 3% in the instrumented runs. Measured E/P speeds are wall-clock averages and include that effect. The emulated runs are noisy (per-pair spread about +-10%, partly from other load on the host), so I used 41 pairs and bootstrap intervals.

## 2. What a chunk costs

`reports/sweep-plain8.json` and `sweep-plain8-b.json`: equal chunks with a test-only `SD_NCHUNKS` override (`tools/mkinst.py --nchunks-env`, `tools/sweep.py`), 8 threads, 7 and 9 interleaved rounds. These sweep builds came from an earlier `mkinst.py` without the MEMK samples.

| Chunks | Wall ms | Index ms | Answer ms | Max RSS KiB |
| ---: | ---: | ---: | ---: | ---: |
| 16 | 185.5 to 196.3 | 134.9 to 142.3 | 30.4 to 32.3 | 55,284 to 56,380 |
| 24 | 187.9 to 195.8 | 134.9 to 140.4 | 32.2 to 34.6 | 55,964 to 55,976 |
| 32 | 192.2 to 198.2 | 137.0 to 139.8 | 34.5 to 37.1 | 55,720 to 55,860 |
| 48 | 194.9 to 204.5 | 137.3 to 141.6 | 39.0 to 41.8 | 58,116 to 58,156 |

Each extra chunk adds about 0.27 to 0.30 ms of answer wall at 8 threads (about 2.3 ms of CPU): every list-term clause of a BOOL query touches every chunk (the df sum, the extend loop, the binary search). That is why the chunk count must not grow at 8 and 12 threads, and why the candidate only doubles it when there is one chunk per thread.

Transposed offsets (`variants/tr.patch`): one shared table `starts[l * nchunks + k]` instead of a per-chunk `offs`, so a clause reads one contiguous row. It cut the answer cost per chunk to about 0.18 ms, but the strided column writes made the index slower as chunks grew, and RSS rose 3.3 MB (`reports/sweep-tr-plain8.json`). Rejected.

## 3. Candidates

`tools/sim.py`, `sim2.py`, `sim3.py` are a toy model (greedy claiming, fixed thread speeds, about 0.002 of the index work per chunk for the answer cost). It ruled out dynamic guided self-scheduling from a byte cursor: with the chunk cost, 30 to 77 pieces were no better than fixed shapes. It also showed that any shape whose chunk count is not a multiple of nthreads loses at uniform speeds.

All variants are text substitutions on `baseline.rs` (`tools/mkcand.py`, `tools/mktr.py`; patches in `variants/`). C = chunk count, m = the baseline's rounds (2 at 8 and 12 threads, 1 at 20).

| Variant | Shape | C at 8 / 12 / 20 |
| --- | --- | --- |
| eq1 | m + 1 rounds of equal ranges | 24 / 36 / 40 |
| tail2, tail3, tail4 | m equal rounds, then one round 1/2, 1/3, 1/4 as large | 24 / 36 / 40 |
| pow2 | N(m + 1) ranges, sizes falling linearly (cut at 1 - (1 - k/C)^2) | 24 / 36 / 40 |
| h21, h31 (final), h41, h52 | max(m, 2) rounds, the last 1/2, 1/3, 1/4, 2/5 as large | 16 / 24 / 40 |
| h31x, h21x | as h31, h21 when m = 1, baseline otherwise | 16 / 24 / 40 |

Screening, paired against the baseline binary (`reports/scr-*.json`, 21 pairs; `reports/multi-*.json`, 41 rounds with all variants in rotating order):

| Variant | plain8 | plain12 | p12 | p20 | RSS at 12 threads |
| --- | --- | --- | --- | --- | ---: |
| eq1 | | | | +3.67% (6/21) | |
| tail2 | +2.88% (3/21) | | -1.13% (11/21) | -8.43% (14/21) | -1.0 MB |
| tail3 | +2.38% (5/21) | | +0.37% (8/21) | -5.51% (15/21) | -1.7 MB |
| tail4 | | | | -4.16% (15/21) | |
| pow2 | +1.64% (8/21) | | -7.66%, -5.69% [-8.4, -2.9] | -3.31%, -2.12% [-7.2, +3.8] | -0.3 MB |
| h21 | -1.25%, +0.25% [-1.3, +0.6] | -1.22%, -1.94% [-2.8, -0.5] | -9.01%, -8.23% [-11.1, -5.8] | -4.22% [-9.0, +0.1] | +0.9 MB |
| h31 | +0.14%, -0.37% [-0.9, +0.2] | -2.00%, -1.11% [-1.9, -0.8] | -0.31%, -1.88% [-5.9, 0.0] | -7.02% [-11.0, -1.5] | -5.5 to -6.9 MB |
| h41 | +1.28% (7/21) | -0.81% (15/21) | +3.22%, +0.22% [-3.0, +2.3] | +2.53%, -4.03% [-10.4, +1.9] | -5.8 to -6.7 MB |
| h52 | +1.18%, +1.12% [-0.2, +1.8] | -1.38%, -0.43% [-1.5, +0.7] | +1.50%, -4.10% [-5.6, -1.9] | -2.80%, -5.67% [-9.0, +1.1] | -5.7 to -6.2 MB |

Where two values are given, the first is the 21-pair screen and the second the 41-round multi run. The tail and eq1 variants add chunks at 8 and 12 threads and lose 1.6 to 2.9% at 8 threads from the answer cost. At 20 threads tail3 = h31 = h31x and tail2 = h21 = h21x (same formula when m = 1).

**Why h31.** h21 cuts the p12 tail most but keeps 12-thread RSS where it was. h31 keeps the chunk count at 8 and 12 threads, wins at p20, does not lose at 8 or 12 uniform threads, and lowers RSS at every thread count. Per-chunk RSS traces (instrumented, 3 runs each) put the peak at the end of the index for the baseline at 12 and 20 threads: all `docs` and `offs` arrays plus the streams of the last chunks. With h31 the last streams are a third as large. At 8 threads h31's peak moves to about 74% of the index (the larger first-round streams) and is still 2 to 3 MB lower. The drop is not linear in the last-round size: 2:1 gave nothing at 12 threads, while 5:2, 3:1 and 4:1 gave 5.5 to 6.7 MB. I did not trace the allocator behaviour behind that step (likely glibc's dynamic mmap threshold). The board's runtime is glibc 2.41 (Debian 13), not 2.34, so the M gain carries some risk.

**Code layout.** Four semantically identical forms of the h31 formula, built without PGO, measured at plain8 in three sessions of rounds in rotating order (`base2` is a second copy of the baseline binary; run B's report was not saved because of a wrong output path, its numbers are from the console):

| Form | Run A, 61 rounds (`multi2-plain8.json`) | Run B, 41 rounds | Run C, 41 rounds (`layout-plain8.json`) |
| --- | --- | --- | --- |
| `k + 2 * k.min(nchunks - nthreads)` (final) | | -0.05% [-0.67, +1.56] | +0.52% [-0.57, +1.48] |
| `3 * k - 2 * k.saturating_sub(..)` (`vsat`) | +1.24% [+0.84, +2.02] | +0.89% [+0.46, +1.73] | +2.01% [+1.02, +3.14] |
| `b * k - (b - 1) * ..` with `b = 3` (`h31`) | -0.50% [-1.24, +0.70] | +0.05% [-1.30, +1.13] | +0.38% [-0.18, +1.72] |
| `m` named, `nthreads * (3 * m - 2)` (`v4`) | | +0.52% [-0.88, +1.29] | +0.98% [-0.55, +2.55] |
| baseline copy (`base2`) | -0.27% [-1.10, +0.57] | | +0.70% [-0.29, +1.70] |

The forms compute the same cuts but compile to different binaries; the `vsat` form was my first final and measured +1.09% [+0.46, +2.64] (11/41) in a 41-pair `emu.py` run before I noticed this. The spread between forms (about 1.5%) is code layout, not the chunking. The board builds with PGO, which lays the code out again, so these local layout effects do not carry over. I kept the shortest form. Local PGO builds were not possible: the system `llvm-profdata` is LLVM 15, rustc 1.92 writes LLVM 21 profiles, and `rustup component add llvm-tools` failed (read-only toolchain, no network).

## 4. Correctness

On the final source (`candidate.rs`, native binary SHA-256 `93bab0ae...a9d`, portable `09f7011c...6ed7`):
- Seed-1 `results.txt` SHA-256 `f86973c2...0927` at SD_THREADS 1, 2, 3, 8, 12, 16, 20, 24 and 32 (`reports/hash-threads.json`), and with the portable build at 8 and 20 (`reports/hash-generic.json`); every emulated run in every report was hash-checked too.
- `experiments/b-filter-parse/check_all.sh`: pass=34 fail=0 xfail=2 at the default thread count and at 1, 12 and 20 threads; the portable build passes at the default and at 20. The xfails are the two known `docs.txt`-without-final-LF fixtures.
- `RUSTFLAGS='-Ctarget-cpu=x86-64' cargo build --release --target-dir /projects/sandbox/.data/tgt-generic` compiles without warnings and has no ymm instructions; the native build has no warnings either.
- Invariants: every cut still goes through the unchanged loop that moves it to a line whose id is a multiple of 64; cuts are monotone, cut(0) = 0 and cut(nchunks) = data.len(); chunks are still sorted by index; the `doc - first <= 1 << 16` assert stays. The largest chunk is 3r/(3r - 2) times the baseline's 16 MiB bound, at most 1.5 times (24 MiB, about 25,000 documents of this generator's mean size of about 950 bytes, far below 65,536).
- S by `rustfmt --edition 2021 --emit stdout track-b/src/main.rs | grep -cvE '^\s*$|^\s*//'`: 561 -> 562 (+1; the brief quotes 560 for the baseline, this command gives 561 on `d9d69e7`).

## 5. Correction to the b-deep-profile conclusion on #20

`experiments/b-deep-profile/README.md` (section 5, branch `b-deep-profile`) concluded that PR #20's board slowdown (`b-mem`, T 0.214 s) was most likely board noise. That no longer holds. PR #28 is #20 without the `mallopt` call and without the 7:3 rounds, and it ran at 174.3, 175.5 and 173.0 ms in three board runs, so #20's +40 ms came from one of those two changes. At 20 threads the rounds formula has m = `data.len().div_ceil(20 << 24)` = 1 on the 254 MB corpus, and with m = 1 its single round gives w = 3j over 3N parts, that is, equal chunks identical to #28's. So if the box runs 20 threads, the rounds were inactive and the fixed 128 KiB mmap threshold (`mallopt`) cost about 40 ms there. PR #29's 32 MiB stream capacity (large separate mappings) was also slower (178.5 ms) with higher M, which fits mappings being expensive on the box. If the box runs 12 threads (m = 2), the rounds were active and either change could be the cause; that is the 12-thread risk of this candidate noted in the summary.

## 6. Reading the probe diagnostic at 20 threads

`b-diag-probe` (`b654bec`) touches `(32 x ap + 512 x [affinity CPUs > ap])` MiB after `results.txt`, split over ap threads, each thread taking 8,192 first-touch faults of 4 KiB. The earlier reading only expected ap = 12. Updated reading, with dM = M_probe - M_control and dT = T_probe - T_control:
- dM about 403 MB: ap = 12, no quota (the RULES.md 6P/12T reading). This candidate then acts as in the plain12 and p12 rows.
- dM about 671 MB: ap = 20, all 20 hardware threads, E-cores included. The old decode rule ("remove 537 MB first if dM is at least that") would misread this as ap = 4 under a quota, because 20 x 33.55 MB = 671 MB = 4 x 33.55 + 537 MB. Tell them apart by T: with ap = 4 the whole program runs on 4 threads and T roughly doubles, while with ap = 20 dT stays near the fault cost.
- dM about 940 MB (403 + 537): ap = 12 from a CPU quota on a 20-CPU affinity mask, so 12 threads float over P- and E-cores (the p12 case, likely the worst for the baseline's 24 equal chunks).
- Fault cost at ap = 20: about (dT - 17 ms) / 8,192 per fault, where 17 ms is the earlier 10 ms memory-bandwidth allowance scaled from 384 to 640 MiB. The probe ends when its slowest thread does, so this is an upper bound set by the E-core threads.

## Files

| Path | Contents |
| --- | --- |
| `baseline.rs` | `track-b/src/main.rs` at origin/speed-demon `d9d69e7` (SHA-256 `0090e1af...47ad`) |
| `candidate.rs` | the committed `track-b/src/main.rs` (SHA-256 `fab3ca51...068f`) |
| `variants/*.patch` | every variant above as a diff against `baseline.rs` |
| `tools/pin.c` | the LD_PRELOAD pinning shim with the start gate (`gcc -O2 -Wall -shared -fPIC -o pin.so pin.c -ldl`) |
| `tools/emu.py` | layouts, paired runs (base and candidate alternate, warmup pair, hash check, rusage, tail metrics, bootstrap interval); output readable by `experiments/b-filter-parse/pair.py` |
| `tools/multi.py` | rounds of several binaries in rotating order against the first |
| `tools/mkinst.py` | instrumented copy (IDX, PHASE, INFO, MEMK lines on stderr) of any variant |
| `tools/sweep.py` | chunk-count sweep with the test-only `SD_NCHUNKS` override |
| `tools/mkcand.py`, `tools/mktr.py` | generate the variants from `baseline.rs` |
| `tools/build.sh` | build a source in a scratch copy of the crate (same Cargo.toml, Cargo.lock, config), native or portable |
| `tools/sim.py`, `sim2.py`, `sim3.py` | the toy scheduling model |
| `reports/val-*.json` | emulation validation, baseline vs itself (instrumented) |
| `reports/iscr-*.json`, `scr-*.json`, `multi-*.json` | screening (instrumented and production builds) |
| `reports/sweep-*.json` | chunk-count sweeps |
| `reports/final-*.json`, `final2-*.json`, `tail-*.json` | final paired runs and final instrumented tails |
| `reports/multi2-plain8.json`, `layout-plain8.json` | code-layout spread |
| `reports/hash-*.json` | seed-1 hash at each thread count |

Reproduce (binaries and scratch files under `/projects/sandbox/.data`, since `/tmp` is wiped between tool calls):

```sh
E=experiments/b-chunks2; C=/projects/sandbox/.data/ch2; B=/projects/sandbox/.data/bin
mkdir -p $C/rep && gcc -O2 -Wall -shared -fPIC -o $C/pin.so $E/tools/pin.c -ldl
$E/tools/build.sh $E/baseline.rs ch2-base && $E/tools/build.sh $E/candidate.rs ch2-cand
python3 $E/tools/mkinst.py $E/baseline.rs $C/inst-base.rs && $E/tools/build.sh $C/inst-base.rs ch2-ibase
for L in plain8 p20 p12 plain12; do
  python3 $E/tools/emu.py --base $B/ch2-base --cand $B/ch2-cand --layout $L --pairs 41 --report $C/rep/final-$L.json
done
python3 $E/tools/emu.py --base $B/ch2-ibase --cand $B/ch2-ibase --layout p20 --pairs 5 --report $C/rep/val-p20.json
python3 $E/tools/mkcand.py $E/baseline.rs $C/cands    # all variants
```
