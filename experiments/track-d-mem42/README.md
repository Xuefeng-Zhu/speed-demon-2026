# D lower peak memory: two-pass CSR load and a byte row index

`baseline.rs` is `track-d/src/main.rs` at `f828bd8` (branch `speed-demon`). `candidate.rs` is the new `track-d/src/main.rs` on branch `d-mem`. All numbers here are from the 8-vCPU sandbox (Xeon, kernel 6.1, THP `madvise`), not from the board. Board run pending.

## Memory breakdown of the baseline

`profile-baseline.rs` is the baseline with phase marks (made by `instrument.py`). Each mark prints the elapsed time and the peak of non-file RSS since the previous mark, then resets `VmHWM`. Non-file RSS is `VmHWM - RssFile`, so the 92 MB mapped `graph.txt` is left out, as on the board. `breakdown.py 11 T` runs it 11 times with `SD_THREADS=T` and reports the mean time and the largest peak of each phase (`reports/breakdown-t8.json`, `reports/breakdown-t12.json`).

| Phase | 8 threads | Peak, 8 threads | 12 threads | Peak, 12 threads | What is live at the peak |
|---|---:|---:|---:|---:|---|
| parse into buckets | 18.8 ms | 38.6 MB | 21.4 ms | 38.8 MB | edge buckets, 8 B per edge |
| CSR build | 14.3 ms | **62.8 MB** | 15.3 ms | 60.5 MB | buckets (40 MB, freed block by block) + `first` 7 MB + `adj` 20 MB |
| renumber | 33.9 ms | 58.4 MB | 33.9 ms | 58.4 MB | old CSR 27 MB + `rank` 7 MB + new forward CSR 27 MB |
| drop old CSR, read queries | 4.4 ms | 32.7 MB | 4.6 ms | 32.8 MB | forward CSR + `rank` |
| relabel | 16.3 ms | 51.9 MB | 18.4 ms | 52.0 MB | forward CSR + backward CSR (`rank` freed before the scatter) |
| queries | 80.3 ms | 60.1 MB | 88.5 ms | **63.4 MB** | both CSRs (53.9 MB) + about 0.8 MB of search state per thread |

So the peak is not one phase. At 8 threads the CSR build is highest; at 12 threads (the board's count) the query phase is, and the build, renumber and query phases are all within 5 MB of each other. Removing the edge buckets alone would not lower the 12-thread peak: the two final graphs themselves are 53.9 MB (`first` 7.0 MB and `adj` 20 MB each).

The board's M for this source family is 82 to 87 MB, about 20 MB above the local peak. Nothing local accounts for that. The sampled peak in `memrun.py` agrees with the `VmHWM` breakdown, so no short peak is being missed. Page tables add 0.4 MB. THP is charged locally too (`AnonHugePages` shows 44 MB in the `MADV_HUGEPAGE` arrays). `thp-emulation.rs` gives every heap block of 128 KiB or more `MADV_HUGEPAGE`, like a host with THP `always`. With it, the bucket lists still had no huge pages (glibc writes each block's header at once) and the peak did not change. So THP `always` on the host is not supported as the cause. Without the fixed mmap threshold (`mallopt`) the candidate's peak goes from 52.4 to 68.1 MB, so allocator retention matters a lot. Some similar effect on the box may explain the gap, but this cannot be checked here.

## The candidate

1. **Load in two passes, no edge list.** `scan` parses each thread's share of `graph.txt` twice. The first pass reads only each line's tail, skips to the next newline (the first byte with bit 5 clear, eight bytes at a time), and counts into `first` with atomic adds. After the prefix sum (`ends`), the second pass parses whole lines and places each edge with an atomic decrement of its tail's cursor. A 16-line ring delays each edge, so that `first[tail]` is prefetched 16 lines ahead and the target slot of `adj` 8 lines ahead. Without the prefetch the place pass took 29 ms; with it, 20 to 21 ms. Load memory is `first` plus `adj` (27 MB) instead of 63 MB.
2. **Byte row index.** `Csr` keeps a u32 start per block of `1 << k` rows plus one byte per row (`at(u) = base[u >> k] + off[u]`). `k` is the largest value up to 6 for which every block's offsets fit in a byte. Road graphs get `k = 6` (the largest 64-row span on seed 1 is 227 edges). A row of 256 edges or more makes `k` smaller, down to `k = 0`, which is a plain u32 per row. The row index shrinks from 7.0 MB to 1.85 MB per graph, so the final graphs take 43.7 MB instead of 53.9 MB. In the sandbox the query phase was 1 to 3 ms slower than with u32 row starts. A layout with a u32 per row plus the byte (forced `k = 0`) was much slower (queries 87 ms), so the cost is in the extra loads, not the size.
3. **Free the old rows early.** `renumber` takes the old graph by value and copies rows as before. After that it frees the old `adj` and builds the new row starts from the old degrees (`f[new id + 1] = degree`, then `ends`). This way the old graph, `rank` and a u32 row-start array are never all live together.

| Phase | 8 threads | Peak, 8 threads | 12 threads | Peak, 12 threads |
|---|---:|---:|---:|---:|
| count pass | 11.2 ms | 6.9 MB | 13.2 ms | 6.9 MB |
| place pass | 21.1 ms | 26.0 MB | 24.7 ms | 26.1 MB |
| pack row index | 3.3 ms | 27.6 MB | 3.3 ms | 27.6 MB |
| renumber BFS and row copy | 32.5 ms | 46.8 MB | 32.8 ms | 46.9 MB |
| new row starts, pack, read queries | 7.8 ms | 46.8 MB | 8.2 ms | 46.9 MB |
| relabel | 19.1 ms | 48.5 MB | 20.3 ms | 48.6 MB |
| queries | 82.9 ms | **50.2 MB** | 88.8 ms | **53.4 MB** |

The peak is now the query phase: 43.7 MB of graphs plus the per-thread search state.

## Checks

- Full seed 1: output SHA-256 `a23dbdf0…277e` on every run, including 1, 3, 5, 8, 12 and 17 threads.
- `smallcheck.py d`: tiny and sample at seeds 2 and 7 match the official reference byte for byte.
- An overflow- and debug-checked build passed `track-d-balanced-frontier/oracle.py` (16,000 random queries), `exhaustive.py` (36,864), `track-d-u32-fallback/thresholds.py`, `track-d-packed32-adj/boundaries.py` (2^21 and 2^21 + 1 nodes), `track-d-balanced-frontier/extremes.py` and `track-d-coarse-radix33/same_bucket.py`.
- `hubs.py` (new) checks 24 graphs with hub rows of 255 to n - 1 edges and blocks whose rows add up to about 255. These force the smaller block sizes of the row index, down to one row per block. All 1,440 answers match an independent Python Dijkstra. The random oracle's dense graphs (up to 64 nodes with about 1,365 edges) also force `k < 6`.

## Memory, time and S (sandbox, not board results)

`memrun.py` interleaves the binaries after a warm-up and samples RssAnon + RssShmem about every 350 µs. Est. M is that peak plus the output size.

| Build | Runs | Wall median | Min | Peak anon | Est. M |
|---|---:|---:|---:|---:|---:|
| baseline `base-d` | 21 | 170.6 ms | 163.0 ms | 63.66 MB | 63.66 MB |
| candidate | 21 | 179.8 ms | 176.5 ms | 52.42 MB | 52.43 MB |
| baseline profile build, 12 threads | 11 | 194.9 ms | 189.7 ms | 65.88 MB | 65.89 MB |
| candidate profile build, 12 threads | 11 | 205.2 ms | 198.6 ms | 55.69 MB | 55.69 MB |

Reports: `reports/memrun-t8.json` and `reports/memrun-t12-profile.json`. The 12-thread rows use the profile builds, which honour `SD_THREADS`, on 8 vCPUs. Two earlier 21-run batches of nearly final sources measured +7.3% (170.3 against 182.8 ms) and +8.5% (167.5 against 181.8 ms). So the time cost is +5% to +9%, about 9 to 14 ms.

S (rustfmt code lines + 7 Dockerfile lines, `sloc.py`): 379 + 7 = 386 → 409 + 7 = 416 (+30).

Keep rule `T1/T0 < (M0/M1)^0.4 × (S0/S1)^0.3`, using the local peak as M (both are far above the 17.9 MB cap):

| Case | T1/T0 | (M0/M1)^0.4 | (S0/S1)^0.3 | Right side | Verdict | Predicted K |
|---|---:|---:|---:|---:|---|---:|
| 8 threads, final batch | 1.054 | 1.081 | 0.978 | 1.057 | passes by 0.3% | +0.1% |
| 8 threads, +7.3% batch | 1.073 | 1.081 | 0.978 | 1.057 | fails | −0.8% |
| 12 threads (profile builds) | 1.053 | 1.070 | 0.978 | 1.046 | fails | −0.3% |

Predicted K uses `K ∝ T^-0.5 × M^-0.2 × S^-0.15`. Locally the change is neutral within noise: the 18% lower peak is about paid for by the extra parse pass, the row-index loads and 30 lines. On the board it gains only if board M falls by more than local M. If the board's extra 20 MB is a fixed amount, board M goes from about 85 to about 74 MB, about −1.5% K at +7% T. If it scales with the local peak, or comes from the build phase's buffers, the gain is larger. Only a board run can tell. Keep the change only if board K improves, and record board M, T and S.

## Board trial plan and split variants

The board runs 12 threads: the harness starts every timed container with `--cpuset-cpus=0-11` (the P-cores; `run_submission.py --cpuset` and `final_scoring.py --run-cpuset` default to `0-11`, and its README lists "6 P-cores and 12 threads"), so `available_parallelism` is 12. Track A's older notes that call 20 threads the board's default are wrong, and the 12-thread rows above are the ones that matter.

Expected value: near zero, negative if the board's extra 20 MB is a fixed amount (about -1.5% K, see above). The trial is a probe of where that 20 MB comes from: if board M falls by more than the local 11 MB, the excess is in the build-phase buffers and the change is kept.

If board K does not improve, splitting the change does not rescue it. From the 12-thread breakdowns above (no new build needed, the phase peaks are measured):

| Variant at 12 threads | Highest phase | Peak | vs baseline 63.4 MB |
|---|---|---:|---:|
| baseline | queries | 63.4 MB | |
| row index only (buckets kept) | CSR build: buckets 40 MB + u32 `first` 7 MB + `adj` 20 MB, as in the baseline; renumber at most 58.4 MB; queries 53.4 MB | about 60.5 MB | -2.9 MB (-4.6%) |
| two-pass load only (u32 row starts) | queries: both graphs 53.9 MB + search state | 63.4 MB | 0 |
| both (this branch) | queries | 53.4 MB | -10.0 MB |

The row index only lowers the 12-thread peak to the old build phase, so it saves about 3 MB. It still pays the three `csr` packs (about 3.3 ms each) and the slower queries (1 to 3 ms), about +6% T, against a break-even of (63.4/60.5)^0.4 x (386/398)^0.3, about 1.010 with roughly 12 more lines: it fails. The two-pass load alone does not move the 12-thread peak at all. Only the combination reaches the query phase's 53 MB, so if the board rejects this branch, the idea is dropped rather than split.

## Tried and not kept

- Prefetching the `adj` slot in the count pass too. The extra load of `first` lines that other threads are updating made the count pass 18.9 ms instead of 12 ms, so that stage only runs in the place pass.
- Ring prefetch distances 32/16 and 16/4 lines instead of 16/8: no change.
- Skipping the rest of a line byte by byte (`position`): count pass 15 ms, against 10.9 ms with the 8-byte skip. Parsing head and weight and throwing them away: about 14.5 ms.
- Writing the byte degree in the row-copy loop so that the new row starts are filled sequentially: no gain, 5 more lines.
- Packing the row index on all threads (two forms): at most 1.5 ms over three packs, for 5 to 9 more lines. A simpler loop that the compiler vectorizes is kept (saves about 0.35 ms per pack).
- Dropping `mallopt`: peak 68.1 MB.
- Releasing a search's distance pool and large heap buckets after a big query (above 512, 1,024 or 2,048 blocks): query-phase peak at most 0.5 MB lower, and up to 30% slower queries at the lowest threshold.
- Keeping a u32 row-start array during the renumbering instead of rebuilding it: renumber peak 55.3 MB against 46.8 MB, for about 4 ms. At 12 threads that peak would be above the query phase, so M rises about 2.5 MB.
- 24-bit edges with the head stored as a delta from the tail: on seed 1, 7.4% of renumbered edges need |delta| ≥ 4096 (13 bits with sign next to the 11-bit weight). That is too many escapes for the hot loop, so this was not built.
