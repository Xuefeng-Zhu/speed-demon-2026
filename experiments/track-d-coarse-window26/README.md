# D coarse-bucket bounded window (unselected)

Baseline is exact selected coarse-64 source SHA-256 `2a2a325a1c87e4bc68c260e0d80353e0b8f1f9a7b5be81b1ffeaaede6d813f9d`. Candidate `8dc0e87b483f997af4e76b9c692d26475009dbedeefdd2048d860d3bd7adea6c` retains the exact 65,536-entry per-direction pool, exact distances, narrow cutoff, touched cleanup and indexed-wide fallback. It groups coarse quotients in a 256-bucket aligned near window with a bitmap; larger quotients remain in the radix overflow pool. All graph data is read at runtime. This is an experimental data-structure change and does not alter the selected code.

Two independent reviews found no concrete defect under nonnegative weights and single-owner queue state. On refill, `far_top` finds the minimum quotient; only overflow radix buckets 0–8 are drained into its aligned window. Avoiding a speculative `far_top` beyond that window keeps `far_last` low enough for later legal future far insertions. The near minimum remains conservative for bidirectional termination, and same-quotient strict decreases are all re-enqueued. Pool exhaustion clears partial search state and triggers the unchanged exact wide rerun. The narrow cutoff keeps quotient shifts and `base+256` within u64. These are proof sketches and finite checks, not an all-input proof. Fixed pool payload is unchanged; near heads and bitmap add 1,056 bytes per heap plus scalar fields/alignment. The whole-container hidden-data 8 GiB cgroup bound remains unproved.

`heap_property.py` passes one million interleaved queue/multiset operations plus a directed refill case where far_last reaches the end of a window, then valid smaller in-window and next-window pushes occur, as well as empty/refill and maximal quotient. `verify.py` passes capacities 0/1/2/15/16/17/65536, each with 16,000 random and 36,864 exhaustive directed oracle queries and cutoff tests; packed/wide n=2^21 boundaries, max-weight chain and 6,000 repeated/unreachable queries also pass. `adversarial.py` checks 10 dense zero-weight/parallel directed graphs and 23,040 all-pairs queries per cap; 4,738,464 repeat expansions and 1,039,433 inverted exact-key pops were exercised. `cross_window.py` repeats dense tests with weights around 16,384/32,768 and u32::MAX, exercising 1,183,537 repeats and 244,201 inversions. `long_bucket.py` passes an 8,191-node same-bucket zero-cycle graph and confirms forced-capacity exact fallback. All tests are finite, not a hidden-input or cgroup guarantee.

One 9-pair and one 15-pair clean shared ARM full-seed screen gave candidate/baseline median wall 0.232802/0.240148 s (3.1% faster) and 0.229708/0.231814 s (0.9% faster), with CPU 1.557857/1.603413 s and 1.555308/1.609537 s. All 52 timed and warmup hashes match the official seed-1 hash. Raw reports preserve every run and flags. ARM/native process RSS results do not establish x86 or official speed or cgroup peak; the marginal wall changes are susceptible to host noise.

## Serialized x86 validation

Run these from this package root on a Linux x86-64-v3 VM with independently generated full seed-1 data and no competing benchmark. Do not run Docker on the Mac, prune containers/images, change sysctls, or use unrelated datasets.

```sh
python3 heap_property.py
python3 verify.py
python3 adversarial.py
python3 cross_window.py
python3 long_bucket.py
python3 compare.py --data /path/to/full-d --build-dir /tmp/d-window26-first --report /tmp/d-window26-first.json --runs 17 --seed 82731
python3 compare.py --data /path/to/full-d --build-dir /tmp/d-window26-repeat --report /tmp/d-window26-repeat.json --runs 17 --seed 62941
```

Compare compiler flags, exact source checksums and every output hash. The comparator measures native process RSS, not parent-cgroup peak. A positive VM result must still receive source review and official practice. The package contains source, scripts, and public hashes only: no datasets, credentials or binaries.
