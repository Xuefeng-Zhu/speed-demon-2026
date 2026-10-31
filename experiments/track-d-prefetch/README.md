# D neighbor prefetch experiment (not selected)

The commands below refer to the standalone Library archive; in this repository,
use the matching scripts under `experiments/track-d-balanced-frontier/` for the
oracle and extreme checks.

The baseline is the current 23ffdfc D source SHA-256 `1022f4d9c9956b17fd054e96a26d09551eff61936a851edf88505e12e2b1946c`. Three isolated variants prefetch the per-worker distance slot of a valid future adjacency entry 1, 2 or 4 entries ahead with x86 `_mm_prefetch` T0. They use only current graph input and preserve the existing balanced bidirectional search. A target-architecture conditional removes the hint on non-x86 machines. Candidate hashes are in `SHA256SUMS`.

**The x86 prefetch path has not run.** A minimal exact intrinsic call typechecked as Windows x86-64 Rust metadata only; that is not a Linux target build or execution test. Before timing, compile the exact Linux source with the scoring-box ISA and run the included independent oracle, exhaustive graph, large maximum-weight chain, duplicate and repeated-query checks. Independent unsafe-pointer review is required before promotion. Valid graph node IDs ensure the hinted distance pointer stays within the allocation. The source computes the address only if an ahead edge exists in the current row. No data, credentials, generated results or caches are included.

On native shared ARM Mac, where the hint is compiled out, all variants and baseline passed 80 random directed graphs / 16,000 independent Dijkstra queries per executable. One warmup and four randomized full-seed measured rotations all matched the published hash. Median baseline/1/2/4 walls were 0.28326/0.28272/0.27914/0.28377 s, respectively; these are scalar non-x86 control observations, not a prefetch speed claim. Process RSS is not official cgroup memory. See `report.json`.

On an AVX2-capable Linux x86-64 host, generate full data independently using `official/generators/d_traverse.py`. Run:

```
python3 compare.py --data /path/to/full-d --report /tmp/d-prefetch.json --runs 9
for n in baseline prefetch1 prefetch2 prefetch4; do rustc --edition=2021 -C opt-level=3 -C lto=fat -C codegen-units=1 -C panic=abort -C target-cpu=x86-64-v3 "$n.rs" -o "/tmp/d-$n"; done
python3 tests/oracle.py /tmp/d-baseline /tmp/d-prefetch1 /tmp/d-prefetch2 /tmp/d-prefetch4
python3 tests/exhaustive.py /tmp/d-baseline /tmp/d-prefetch1 /tmp/d-prefetch2 /tmp/d-prefetch4
python3 tests/extremes.py /tmp/d-baseline /tmp/d-prefetch1 /tmp/d-prefetch2 /tmp/d-prefetch4
```

The randomized comparator verifies each full hash and records wait4 wall, CPU and process RSS; it is not an official cgroup score. Do not benchmark concurrently. No Mac Docker was used.
