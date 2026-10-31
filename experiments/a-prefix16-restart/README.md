# Track A prefix hash with bounded restart (experimental, not selected)

During each parser shard's first pass, the candidate hashes the endpoint's first 16 bytes and full length, while retaining exact full-byte comparison for every hash match. If any open-addressing probe exceeds 48 occupied entries, that shard discards its partial result and restarts once using the original full endpoint hash. A completed prefix-hash shard rebuilds its names/table in original ID order with the baseline hash before any cross-shard merge; this makes successful and restarted shards use identical canonical hashes. No input distribution, endpoint identity or answer is hard-coded.

Baseline SHA-256 `16ae5a2e4df27269dbcc2f7b21bb9ad1022081d84e68e5b2c3f5b122a7cb04e2`; candidate `230ba9c06a1059306a3672f231e0d40973376de7be2acd706fcd6bd1b2732d7f`. A targeted review found no defect in exact equality, capped probing/restart, rehash/growth, hash reconstruction or cross-shard normalization. The new weak hash may collide often on hostile valid inputs; the probe cap causes that shard to reprocess using the unmodified baseline hash, so extra work and memory remain input-dependent. This is unselected pending x86 and official evaluation.

Randomized native shared-Mac ARM pairs at 12 workers gave candidate/baseline median wall 0.058636/0.073715 s (9 pairs) and 0.036591/0.037897 s (15-pair repeat); CPU 0.205506/0.214904 s and 0.189108/0.190579 s respectively. All 52 full seed-1 outputs including warmups matched the published hash. The repeat is about 3.45% lower wall with only 0.8% lower CPU and large shared-host variability; it is not an x86 or official speed claim. `screen.json` and `repeat.json` record individual native timings and hashes of test copies; those copies changed only Linux MAP_ANONYMOUS 0x20 to Darwin 0x1000. No Docker was used.

Candidate and a test-only forced-zero weak-hash build passed the 2,422-endpoint collision/growth reference suite at workers 1/2/3/7/12/32, with fallback traces observed. Candidate also passed synthetic 0/1k/100k/100k, 14 page-edge fixtures and the 132,624-group grid at workers 1/2/6/12/64. `run-properties.py` checks all endpoint lengths and alignments, exact 48/49-probe cutoff, >2,048-entry growth and stable IDs, shard restart, and canonical hashes across differing shard orders. A mixed-shard fixture confirms exactly one fallback and reference-correct merging with a successful prefix-hash shard. The numeric parser is byte-identical to baseline and intentionally uses release wrapping arithmetic; property script limits overflow-checked tests to zero-latency/hash-only cases.

## Target testing

On a disposable x86-64-v3 Linux VM, with separately generated full seed-1 data and no competing benchmarks:

```
python3 run-properties.py
rustc --edition=2021 -O -C lto=fat -C codegen-units=1 -C panic=abort -C target-cpu=x86-64-v3 candidate.rs -o /tmp/a-prefix
python3 tests/test.py --binary /tmp/a-prefix --io directories
python3 tests/page_end_test.py --binary /tmp/a-prefix --reference official/reference/a_ingest.py
python3 tests/latency_grid_test.py --binary /tmp/a-prefix
python3 make-forced.py --source candidate.rs --output /tmp/a-prefix-forced.rs --zero-weak --trace
rustc --crate-name a_prefix_forced --edition=2021 -O -C lto=fat -C codegen-units=1 -C panic=abort -C target-cpu=x86-64-v3 /tmp/a-prefix-forced.rs -o /tmp/a-prefix-forced
python3 tests/stress-growth.py --binary /tmp/a-prefix --binary /tmp/a-prefix-forced --reference official/reference/a_ingest.py
python3 make-forced.py --source candidate.rs --output /tmp/a-prefix-trace.rs --trace
rustc --crate-name a_prefix_trace --edition=2021 -O -C lto=fat -C codegen-units=1 -C panic=abort -C target-cpu=x86-64-v3 /tmp/a-prefix-trace.rs -o /tmp/a-prefix-trace
python3 mixed-shards.py --binary /tmp/a-prefix-trace --reference official/reference/a_ingest.py --require-restart-marker
python3 compare.py --data /path/to/full-a --report /tmp/a-prefix-pairs.json --runs 15 --threads 12
```

`compare.py` compiles the exact baseline and candidate with matching flags, randomizes paired order and checks each full output hash. Native process RSS and shared-VM wall times are not official cgroup measurements. Repeat target timing before an official practice candidate; never rely on the seed-1 distribution for correctness.

## Dot VM x86 comparison

The parent-run shared native x86 VM did not find a stable wall-time winner. Across this, C AVX2 and D chain packages, 300 full hashes, 24 alternate references and actual SIMD, guard, collision and graph transformation oracle checks passed. This remains unselected.
