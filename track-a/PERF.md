# Track A: performance log

Every step from the reference to the current version. The board run IDs will be added once each step has run on the live board. Until then, the numbers below come from local runs.

**How these were measured.** The local machine is arm64 (Neoverse-V2) with 2 cores and about 7 GB of RAM, and other workloads were running on it (load average 2 to 4). Wall times there are noisy and only relative. Each "wall" figure is the minimum of 8 to 10 runs on full seed 1 (3.1M lines, 239 MB, file in page cache). "CPU" is process CPU time per phase, from a separately instrumented build (`clock_gettime(CLOCK_PROCESS_CPUTIME_ID)` at phase boundaries), with `SD_THREADS=1` and the minimum of 8 to 10 runs. "RssAnon" is the peak anonymous RSS read from `/proc/self/status` at phase boundaries. The board measures cgroup `memory.peak`. Our mapped input pages are already charged to the pre-warm, so they do not count there, but about 10 MB of page cache for `summary.txt` will.

| Step | Change | Run ID | Local wall (2 threads) | CPU (1 thread) | RssAnon peak | Board T (s) | Board M (MB) |
|---|---|---|---|---|---|---|---|
| 0 | Reference, unchanged (Python) | (calibration) | 51.0 s (full seed 2, same machine) | – | – | 32.05 | 228 |
| 1 | Rust, std only: mmap, a parse thread per chunk making `(key, latency)` records, a global counting-sort scatter, per-group selection, parallel formatting | to add | 191 ms | about 180 ms total | about 42 MB | | |
| 2 | Records bucketed by hour, work handed out by hour; no global cursor or latency arrays; per-thread `MADV_POPULATE_READ` in place of serial `MAP_POPULATE` | to add | 130 ms | parse 142, summarise+write 49 | 25 MB | | |
| 3 | Unchecked word loads (one assert, then `read_unaligned`); endpoint compare by words, not a `memcmp` call | to add | about the same | parse 134 to 143 (noise) | 25 MB | | |
| 4 | Write overlapped with summarising: workers send finished hours over `mpsc`, main writes them in order | to add | 128 ms | summarise+write 47 | 25 MB | | |
| 5 | Selection order p50, then p95 on the right part, then p99 on its right part (about n + n/2 + n/20 values in place of about 3n) | to add | 117 to 128 ms | summarise+write 43 to 46 | 25 MB | | |
| 6 | Line-count cut, same speed: 266 to 165 code lines (rustfmt + scc rule). See the note below | to add | same as step 5 within noise | parse slightly lower, summarise+write slightly higher, total about the same | about the same | | |

## Step 6: fewer lines, same speed

Goal: shrink `src/main.rs` without slowing it down, since lines weigh 0.15 and time 0.50 in K. The count is code lines after default rustfmt (comments and blank lines are free). It went from 266 to 165.

What changed:
- A small `par(n, f)` helper replaces both hand-written thread-spawn blocks.
- The global merge table is gone. The names from all threads are sorted and deduplicated, and each thread's ids map to ranks by binary search (about 1,842 × T lookups, well under 1 ms).
- The per-thread endpoint table is a fixed 8,192 slots. The spec has exactly 1,842 endpoints per seed, and an assert stops the program past 4,096. The grow-and-rehash path and the stored hash are gone.
- Records are `id << 33 | latency << 1 | is_5xx`. Summarise pushes `latency << 1 | is_5xx` into per-endpoint vectors that are reused across hours. This replaces the two-pass counting sort and the separate error counters: the values still sort by latency, and errors are the sum of the low bits.
- Hours are assigned by stride (worker t takes t, t+T, ...), not by an atomic counter. Each worker has its own channel, so the main thread reads hour h from channel h mod T and writes in order with no pending buffer. The write still overlaps the summarising.
- The three selections no longer need guards (`v[r50..]` rather than `v[r50 + 1..]`), and the small-group sort is gone.
- The latency parser has one path: SWAR on the first 8 digits, then a loop for a 9th and 10th digit.
- `push_num` is a 5-line recursive formatter.
- The mmap constants are written inline with a comment.

What was tried and put back, because it cost time:
- `writeln!` formatting cost about +15 ms CPU per run. The hand formatter stays.
- Bounds-checked `u64::from_le_bytes(d[i..i + 8])` loads cost about +10 ms of parse CPU. The asserted `read_unaligned` load stays.
- Plain slice `==` for endpoint compares cost about +5 to 10 ms of parse CPU. The word-wise `same` stays, in a shorter form.
- A scalar-only latency parser cost about +6 ms. The SWAR path stays.
- Rewriting the hash loop as `while k == 8`, or with a `u128` mask, cost +40 to 50 ms of parse CPU. The codegen is sensitive here, so the loop keeps its `loop { … if k < 8 { break } }` shape.
- Dropping `#[inline(always)]` from `load` cost about +40 ms. It is now the only one left, and the others made no measurable difference.
- A spin-wait "write when it is your turn" in the workers in place of channels was slower under CPU contention. It was dropped.

How it was measured: the shared 2-core box was heavily loaded by other benchmarks (load average 4 to 6), so wall times swung by 2× between runs. The checks were alternating runs of old and new binaries. One was process CPU per phase with `SD_THREADS=1` (minimum of 10 to 12 runs): old 151 ms parse and 199 ms total, new 143 ms and 195 ms. The other was full 2-thread runs, alternating, in three sets of medians of 3: wall 370/358/322 ms for the old binary against 356/302/301 ms for the new, and CPU 215/214/220 against 211/215/216 ms. A 12-run set gave wall medians of 297 against 294 ms. These are the same within noise, with no sign of a slowdown. There are no board numbers yet.

## What the phases cost (step 5, 1 thread, CPU ms)

| Phase | CPU ms | Note |
|---|---|---|
| parse (includes page-table population, about 25 to 50 ms of it sys time) | 129 | parallel, scales with threads |
| merge endpoint tables and sort the names | 0.3 | serial |
| summarise and write | 41 to 50 | parallel, plus a serial write that overlaps it |

## Where step 1's time went, and why step 2 exists

Step 1, as wall ms on 2 loaded cores: map with `MAP_POPULATE` 17 to 25 (serial); parse 140; merge and cursor computation 12 (serial: 12 threads × 132k counters); scatter 10 to 18; selection and formatting 30 to 45; write 10 (serial). The serial parts would dominate on a 12-thread box. Step 2 removed the cursor merge. Each hour's latencies are now counting-sorted by the worker that owns that hour, so the global `(thread, group)` prefix sums are gone. It also dropped the 12 MB global latency array and moved page-table population into the threads.

## Failed or neutral experiments

- **Branch-free first 48 bytes of the endpoint.** Six word loads, a movemask built with multiplies, independent per-word multiplies for the hash, and a loop only past 48 bytes. The aim was to remove the loop-exit misprediction. Parse CPU went from 145 and 131 ms to 154 and 155 ms on alternating runs, so it was slower. The fixed extra work cost more than the misprediction it saved. Reverted.
- **Word-wise name compare in place of `memcmp`.** No measurable change (143 against 142 ms). It is kept because it avoids a library call for 20 to 80-byte strings. Replacing the compare with a length-only check (wrong, timing only) saved about 18 ms of parse CPU. That is the price of exact matching rather than trusting a 64-bit hash, and we pay it on purpose.
- **Sort threshold for small groups.** 64 instead of 16 made no difference. Fully sorting every group in place of selecting cost +13 ms CPU (57 against 44).
- **Lazy page faults against `MAP_POPULATE`.** No clear difference given the noise. The final version uses per-thread `MADV_POPULATE_READ`, which falls back to lazy faults on kernels older than 5.14.
- **No selection at all** (wrong, timing only): summarise went from about 46 to 29 ms CPU, so selection is about 17 ms of CPU per 3.1M values.

## Board estimate (not measured)

Total CPU is about 170 to 190 ms. With 6 P-cores and 12 threads at 2.5 GHz (turbo off), and a serial part of under 1 ms plus process start, we expect T of roughly 25 to 45 ms, against a T_ref of 32 s. M should be about 25 MB of anonymous memory plus about 10 MB of output page cache plus container overhead. These are estimates until the board run IDs are in.
