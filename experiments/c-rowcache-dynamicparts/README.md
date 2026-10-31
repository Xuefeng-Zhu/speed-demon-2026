# C dynamic owner partitions on row-cache baseline (unselected)

Exact baseline `baseline.rs` SHA-256 `76b341e2b7e880fe4ceeee220206a63b48cd247bba4448aa7991a7ad825e8dd2`. `parts4.rs` SHA-256 `bcd4d7715bffd8a3dc062cad6e7aa0886a96d659fcc9170735c4d4d123f67eae` uses up to four times as many hash-based owner partitions as worker threads (bounded at 128, but never below the worker count) and lets each reducer claim partitions by atomic ticket. Each partition still has exactly one owner dictionary, cache, and group bitmap. Equal names have equal full hash and always route to the same partition; dictionary exact equality and full-collision promotion are unchanged. Output counts sum across reducer workers. The unmodified large-file/group fallback remains selected before parsing and output. `parts2.rs` is the analogous two-times variant; neither variant is selected. This rebases older `experiments/c-owner-moreparts/` on the fused-name / row-cache implementation.

Native macOS ARM, generated public full seed 1, randomized 15-pair batches per variant, warmups included: four-times candidate/baseline median wall `0.072049/0.086071` and `0.067502/0.071054` seconds; median CPU `0.425725/0.455123` and `0.425198/0.434217` seconds. Median process RSS (not cgroup) was about `297/287 MB` and `299/287 MB`. The first batch had an elevated baseline, so results vary and do not establish target x86 or official scoring. Two-times batches were 2.4% and 0.1% faster in wall with 2.0% and 1.6% less CPU; no compelling benefit. The full output hash matched across all 128 measured and warmup executions; raw observations are preserved in `parts*-arm*.json`. Each variant also passed 24 mixed corpora × 5 worker counts against `official/reference/c_join.py`; the four-times variant passed 8 additional forced-all-zero-hash corpora × 5 counts. These do not exhaust valid schedules, establish worst-case memory, prove >4 GiB full parsing, or exercise target x86 SIMD. Additional bin vectors and repeated dictionaries add memory and allocation costs. Same-full-hash names remain concentrated in one partition as before; randomized dictionary hashing is not a worst-case time guarantee.

To test on compatible x86-64-v3 hardware, extract at archive root, independently generate seed-1 full C input, check AVX2 support, then run serially:

```
python3 experiments/c-rowcache-dynamicparts/verify.py --avx2
rustc --edition=2021 -O -C lto=fat -C codegen-units=1 -C panic=abort -C target-cpu=x86-64-v3 experiments/c-rowcache-dynamicparts/baseline.rs -o /tmp/c-dyn-base
rustc --edition=2021 -O -C lto=fat -C codegen-units=1 -C panic=abort -C target-cpu=x86-64-v3 experiments/c-rowcache-dynamicparts/parts4.rs -o /tmp/c-dyn-parts4
python3 experiments/c-rowcache-dynamicparts/compare.py --baseline /tmp/c-dyn-base --variant /tmp/c-dyn-parts4 --data /path/to/full-c --runs 15 --report /tmp/c-dyn-parts4.json
```

Repeat the 15-pair comparison with target RSS/cgroup checks and forced-collision/boundary cases. No Mac Docker was used.

Independent static review of exact `parts4.rs` found no concrete routing, ticket-claim, thread-safety, output aggregation, or fallback defect under the competition and practical OS worker limits. It confirmed parser joins before read-only handoff; all in-range tickets are uniquely assigned by relaxed fetch-add; each claimed dictionary is private, and reducer counts sum independently of scheduling. The check does not prove total memory under 8 GiB, arbitrary thread-count counter non-wrap, or schedule exhaustion. Equal-full-hash families still concentrate on one owner. Further targeted x86 tests should force one owner, long names, repeated and empty boundaries, sparse/uneven groups and large worker counts.

The archive also includes adapted adversarial scripts for the exact dynamic candidate; execute on dot VM after inspecting CPU features:

```
python3 experiments/c-rowcache-dynamicparts/edge.py --avx2
python3 experiments/c-rowcache-dynamicparts/collision.py --avx2
python3 experiments/c-rowcache-dynamicparts/cut_oracle.py --avx2
python3 experiments/c-rowcache-dynamicparts/gate.py
```

These adapted scripts were packaged for target verification; they have not yet been run against this exact source. Their existence does not constitute a passing result.
