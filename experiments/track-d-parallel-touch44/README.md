# Track D: parallel huge-page first touch, divide-free bucket index

Based on production `043081c` (`track-d/src/main.rs` unchanged since `cb9c687`, PR #42). `baseline.rs` is that source.

## Change

1. `zeros()` still gives every 2 MiB page of a new array exactly one first writer (the de693db fix for the huge-page fault race), but the writers are now `threads` threads, each taking every `threads`-th page, instead of the main thread alone. Four `zeros()` calls (the file-id CSR and the renumbered CSR, 27 MB each) made the main thread take about 25 huge-page faults in a row, each zeroing 2 MiB in the kernel; a timer around each call measured 3.3 to 5.1 ms of serial `zeros()` time per run on the VM, while the other threads waited.
2. The parse loop picks an edge's bucket with `(u as u128 * inv >> 64)`, where `inv = 2^64 / block_len + 1`, instead of `u / block_len`. This is exact for every u32 `u` because `block_len < 2^32`, and replaces one 64-bit division per edge (5 million per run) with one multiply.

Formatted code lines 382 to 385; official `static_axes.py` S 389 to 392. The arrays, their huge-page advice and the output are unchanged.

## Local measurements (team x86 VM, not official)

Azure Xeon Platinum 8573C VM, runs pinned to CPUs 0-11 (6 cores x 2 threads, like the board's cpuset), interleaved in random order, every output hash-checked. `kbench.py` is the harness.

| Run | Seed 1 paired median | Seed 2 paired median |
|---|---:|---:|
| final source, 40 rounds (`bench-d-cand-zd.txt`) | -3.05% (126.35 to 122.04 ms) | -2.87% (128.05 to 124.34 ms) |
| same edits from `mkvar.py`, 40 rounds (`bench-d-1.txt`, `zd`) | -2.74% | -3.40% |
| same edits, 40 rounds, later batch | -3.07% | -2.98% |

Each part alone, 40 rounds (`bench-d-1.txt`): parallel first touch -2.15% / -2.88%, multiply instead of divide -1.98% / -0.90%.

Cgroup `memory.peak` (fresh cgroup per run, 12 rounds, `mem-d-cand-zd.txt`): seed 1 median 70.31 to 70.21 MB, max 71.01 to 71.22 MB; seed 2 median 69.56 to 69.77 MB. No change expected or seen.

This VM has overstated CPU-side gains for the board by about a third before, so expect roughly -2% T on the board, about +0.9% K after the 3 extra lines. That is below the board's 3-5% noise, so two runs will not resolve it on their own.

Tried and not kept in the same session (VM, 30-40 rounds each): prefetching the head's rank entry 16, 32 or 64 edges ahead in `relabel` (alone -1.5% / -2.1%, but nothing on top of the two changes above); a branch-free `reach` that writes every relaxation's result with `select_unpredictable` and always takes the meeting minimum (-0.25% / -0.08%); a two-phase `relabel` where each thread updates the counts of its own node span with plain loads and stores and only edges into other spans use atomics (-0.7% / -1.3% alone, -2.4% / -3.0% with both changes above, so no gain over them).

## Correctness

- Full seeds 1, 2 and 3 (seed 3 generated with the official generator, expected output from the official reference): byte-identical, with CPU affinity 0, 0-1, 0-2, 0-4, 0-6, 0-7, 0-11 and 0-15 (Track D sizes its thread count from the affinity mask).
- `dcheck.sh` (the PR #42 `checks.sh` suite run natively): overflow- and debug-checked build passed the random oracle (16,000 queries), exhaustive three-node graphs, same-bucket graphs, u32 cutoff thresholds, 2^21 and 2^21 + 1 node boundaries, the maximum-weight chain and 6,000 repeated and unreachable queries; the first three again pinned to CPU 0 and CPUs 0-2. A release build matched the official reference on tiny seeds 2, 17, 4242 and sample seeds 2, 7.
- `rustfmt --check` clean.
