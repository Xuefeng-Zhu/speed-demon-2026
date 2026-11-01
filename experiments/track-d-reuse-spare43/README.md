# D backward graph in the file-id graph's arrays

`baseline.rs` is `track-d/src/main.rs` at `2026af8`: production D, with the one-first-writer-per-huge-page fix of `de693db` (SHA-256 `ed48a6b9…0536`). The candidate is `track-d/src/main.rs` on branch `d-reuse-spare` (SHA-256 `bedb711e…3252`). It changes only where `relabel` puts the backward CSR.

**Before.** `main` dropped the file-id graph `g` right after renumbering, and `relabel` then allocated two new zeroed arrays, `zeros(n + 1)` and `zeros(m)`: exactly the sizes of `g`'s arrays. Since `de693db`, the main thread writes one byte into every 2 MiB page of a new `zeros()` array before any worker touches it. So each run paid two unmaps (`g`'s arrays), two new mappings and about 11 serial huge-page faults (about 22 MB zeroed by the kernel) before the relabel workers started.

**After.** `g` is passed to `relabel` as `spare`. Its row array is cleared with `fill(0)` (7 MB) and holds the in-degree counts; its edge array is overwritten by the scatter. Nothing new is mapped or faulted in. Formatted code lines are unchanged at 382, so the expected board S stays 389.

**Why it is correct.** Nothing reads `g` after `renumber` returns. `g.first` has n + 1 entries and `g.adj` has m, the sizes the backward CSR needs. After `fill(0)` the counts start from zero, as they did in the new zeroed array. `ends` turns them into running ends; index n has no in-edges, so it ends at m. The scatter then places all m edges, one per slot, so every slot of `adj` is written before a query reads it.

## Checks

- `python3 check.py d` on full seed 1: allowlisted images, offline build, sandboxed run, published SHA-256 (ARM Linux container).
- The same image pinned to 1, 3, 5 and 8 CPUs (`--cpuset-cpus`) gave the published hash each time.
- `checks.sh` (log: `checks.log`): an overflow- and debug-checked build passed the random oracle (16,000 queries), exhaustive three-node (36,864), same-bucket (46,336), u32 cutoff thresholds, 2^21 and 2^21 + 1 node boundaries, the maximum-size maximum-weight chain and 6,000 repeated and unreachable queries. The first three suites passed again pinned to 1 and 3 CPUs. A release build matched the official reference on tiny seeds 2, 17 and 4242 and sample seeds 2 and 7.

## Timing and memory

`bench.sh` builds probes of both sources with `make_probe.py`, which adds phase marks, cgroup readings and an `SD_THREADS` override, and runs them alternately under the `check.py` restrictions on full seed 1. `paired.py` summarises a report. Machine: ARM Linux in OrbStack, 8 vCPUs on an Apple M2, load average 7 to 11 during the runs. `SD_THREADS=12` matches the board's thread count but oversubscribes the 8 vCPUs. These are not board numbers.

| Batch | Pairs | Relabel window, paired median (candidate faster) | Whole run, paired median (candidate faster) | Cgroup peak, medians | THP faults per run |
|---|---:|---:|---:|---:|---:|
| 8 threads, `report.txt` | 21 | −1.02 ms (13/21) | +7.7 ms (8/21) | 65.90 → 65.87 MB | 32 → 21 |
| 12 threads, `report.txt` | 21 | −1.39 ms (14/21) | −1.7 ms (13/21) | 68.54 → 68.45 MB | 32 → 21 |
| 8 threads, `repeat.txt` | 31 | −0.84 ms (21/31) | +4.2 ms (13/31) | 65.72 → 65.74 MB | 32 → 21 |

The relabel window runs from the end of `renumber` to the end of `relabel`; it is the only part of the run the change touches, and it is about 1 ms shorter in all three batches. The whole-run differences go both ways and come from phases that run identical code on identical data: in the first 8-thread batch, per-pair differences in the query phase ranged from −19 to +110 ms, and in the 31-pair repeat the query phase differed by −0.33 ms (candidate faster in 16/31). Peak memory is unchanged, as expected: `g`'s pages replace an allocation of the same size. In every pair the candidate had 8 to 13 fewer huge-page faults (median 10 to 11); `thp_fault_alloc` counts the whole VM, so other activity adds a little noise.

Expected board effect: about 1 ms, which is 0.7% of T at about 147 ms and +0.3% K, at the same M and S. One board run cannot resolve that: board runs of the unchanged production D source since `de693db` include T = 146.3, 149.3 and 157.1 ms, and M from 69.4 to 83.7 MB.

To repeat the timing, with full seed-1 data in a Docker volume named `sd-d-data`:

```sh
experiments/track-d-reuse-spare43/bench.sh 21 "8 12" sd-d-data > /tmp/report.txt
python3 experiments/track-d-reuse-spare43/paired.py /tmp/report.txt
```
