# Track A: parse the latency before the endpoint lookup

Based on production `043081c` (`track-a/src/main.rs` from PR #49). `baseline.rs` is that source.

## Change

In `parse`, the latency, the next line's start and the 5xx bit are computed before the endpoint hash and the dictionary lookup instead of after them. Nothing else changes: same loads, same hash, same exact name compare, same records.

The parse loop is one dependency chain: a line's start is known only once the previous line's latency has been parsed. Computing `next` first puts the next line's address into the instruction stream before the dictionary probe, so the out-of-order core can start the next line's loads while the probe's cache misses are outstanding. `experiments/a-lookup-latency-order/` screened the same reorder on an older source on ARM (about -6% wall there) but it was never run on x86 or the board.

S is unchanged (official `static_axes.py`: 419; one comment line added).

## Local measurements (team x86 VM, not official)

Azure Xeon Platinum 8573C VM, CPUs 0-11, interleaved random-order rounds, every output hash-checked (`kbench.py`).

| Run | Seed 1 | Seed 2 | Seed 3 |
|---|---:|---:|---:|
| 30 rounds | -3.01% (20.17 -> 19.63 ms) | -2.07% (20.07 -> 19.69 ms) | |
| 40 rounds (`bench-a-lat1.txt`) | -1.54% (20.14 -> 19.71 ms) | -1.08% (20.01 -> 19.73 ms) | -1.70% (20.14 -> 19.77 ms) |
| 1 thread, 12 rounds | -1.80% (134.9 -> 132.4 ms) | | |
| 6 threads on 6 cores, 20 rounds | -1.53% (26.95 -> 26.54 ms) | | |

Cgroup `memory.peak`, 12 rounds (`mem-a-lat1.txt`): seed 1 median 21.78 -> 21.33 MB, seed 2 21.55 -> 21.81 MB, i.e. unchanged.

Expect about -1% to -1.5% T on the board (+0.5% to +0.75% K at the same S), below one run's noise.

Probes from the same session, not proposed: replacing the dictionary lookup with a fake id (wrong output) made the 12-thread run 16% faster and one thread 9% faster, so the lookup is the largest single cost after the byte scan; aligning each dictionary entry to 64 bytes (1 MB instead of 622 KB) was 2% slower; `mallopt(M_MMAP_THRESHOLD)` at 64 or 128 KiB cut the VM cgroup peak 0.7-1 MB but cost 1.5-2.3% T over 40 rounds x 3 seeds; 8 summary workers instead of 11 cut it 0.8 MB at +0.3% to +1.4% T; a static glibc build changed nothing for A (and was 17% slower for C).

## Correctness

- `experiments/a-x86-speed/check.py`: full seed 1 at SD_THREADS 1, 2, 3, 6, 8, 12 and default, `test.py`, `page_end_test.py`, `latency_grid_test.py`, sample seeds 2, 98, 999, 4242 against the official reference: 0 failures.
- `experiments/a-x86-speed/adversarial.py --spec` (endpoint lengths 1-125 under every method, 1,842 distinct endpoints, boundary latencies, groups of every size 1-200) at 1, 2, 3, 7 and 12 threads: 0 failures.
- Full seeds 2 and 3 (official generator; expected output from the official reference) at SD_THREADS 1, 2, 5, 7, 12, 13 and 16: byte-identical.
