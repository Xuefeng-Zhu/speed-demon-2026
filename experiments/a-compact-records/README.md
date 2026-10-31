# Track A compact per-hour record stream (experimental)

Against exact selected baseline SHA-256 `16ae5a2e4df27269dbcc2f7b21bb9ad1022081d84e68e5b2c3f5b122a7cb04e2`, candidate `4af40353f517f566217b0f882ec25d8002f61d211dcc479c53f8a1dd5de7ed88` stores a normal record in 32 bits: 11-bit local endpoint ID, one 5xx bit and 20-bit latency. For ID ≥2048 or latency ≥1,048,575, it emits `u32::MAX` and appends the original full 64-bit record to the corresponding chunk/hour escape vector. Strict latency inequality means no ordinary value aliases the sentinel. Each summary pass independently consumes escapes in the same chunk/hour order; exact endpoint equality, local/global rank mapping, percentile and output logic are unchanged. No input-specific identity or answer is assumed.

Two randomized native shared-Mac ARM 12-worker paired screens after warmup gave candidate/baseline median wall 0.040221/0.040739 s (11 pairs) and 0.039443/0.042817 s (15 pairs); CPU 0.185838/0.188019 s and 0.189243/0.193480 s; native RSS medians ~273/286 MB. All 56 full hashes including warmups matched. These are noisy native ARM measurements with a temporary Darwin anonymous-map flag, not x86, official or cgroup scores. Seed 1 had 36,447 latency escapes out of 3.1M records (1.18%); no assumption about that fraction is needed for correctness. The candidate remains unselected pending x86 and official validation.

Independent review found no sentinel, escape order or dual-summary-pass defect. Exact-source properties checked 49,440 combinations including ID 2047/2048, latency 1,048,574/1,048,575 and u32 maximum, status 499/500/599 and ordered escapes. Independent reference checks passed empty, 40,000 all-escape, 40,000 alternating, and 87,192 records across 2,422 endpoints with 1/2/3/7/12/32 workers; test instrumentation confirmed 13,464 escapes due to local IDs ≥2048. The candidate also passed 0/1k/100k/100k synthetic references, 14 page-edge fixtures, the 132,624-group grid at 1/2/6/12/64 workers, and the synthetic reference suite with all endpoint hashes forced equal. These tests used native Darwin map-flag adaptation; actual x86 execution remains untested.

Worst-case all-escape records have 12 payload bytes per record (4-byte sentinel plus original 8-byte record), versus 8 for baseline: 37.2 vs 24.8 MB for 3.1M records before vector slack and other memory. A generated 3.1M identical all-escape corpus matched the exact output at one and 12 workers. In three paired native ARM samples after warmup, maximum process RSS was candidate/baseline 232,669,184/193,298,432 bytes at one worker and 211,304,448/198,328,320 at 12. This includes the 151.9 MB input mapping and is **not** cgroup peak or a formal upper bound; `all-escape.json` retains samples. The grammar permits at most 177 bytes per line, so 3.1M valid lines map at most 548.7 MB plus padding. Other vectors, capacities, outputs and runtime also count toward the official 8 GB cap; measure actual target cgroup memory, including all-escape stress. `all-escape.py` creates and removes a disposable input and checks exact output.

## Required target validation

From archive root on a disposable Linux x86-64-v3 VM, with independently generated full seed-1 input and no competing benchmark:

```sh
python3 experiments/a-compact-records/run-properties.py
for n in baseline candidate; do rustc --edition=2021 -O -C lto=fat -C codegen-units=1 -C panic=abort -C target-cpu=x86-64-v3 "experiments/a-compact-records/$n.rs" -o "/tmp/a-compact-$n"; done
python3 experiments/a-compact-records/make-test-variant.py --trace --output /tmp/a-compact-trace.rs
rustc --edition=2021 -O -C target-cpu=x86-64-v3 /tmp/a-compact-trace.rs -o /tmp/a-compact-trace
python3 experiments/a-compact-records/stress.py --binary /tmp/a-compact-candidate --instrumented /tmp/a-compact-trace --reference official/reference/a_ingest.py
python3 experiments/a-compact-records/make-test-variant.py --forced --output /tmp/a-compact-forced.rs
rustc --edition=2021 -O -C target-cpu=x86-64-v3 /tmp/a-compact-forced.rs -o /tmp/a-compact-forced
python3 track-a-verification/test.py --binary /tmp/a-compact-forced --io directories
python3 track-a-verification/test.py --binary /tmp/a-compact-candidate --io directories
python3 track-a-verification/page_end_test.py --binary /tmp/a-compact-candidate --reference official/reference/a_ingest.py
python3 track-a-verification/latency_grid_test.py --binary /tmp/a-compact-candidate
python3 experiments/a-rust-percentiles/compare.py --baseline /tmp/a-compact-baseline --candidate /tmp/a-compact-candidate --data /path/to/full-a --report /tmp/a-compact-x86.json --runs 15 --threads 12
python3 experiments/a-compact-records/all-escape.py --baseline /tmp/a-compact-baseline --candidate /tmp/a-compact-candidate --report /tmp/a-compact-all-escape.json
```

`run-properties.py` intentionally compiles with release overflow semantics because the original SWAR arithmetic wraps. Test files and the comparator have no datasets, credentials or cached answers; the independent all-escape expected line is calculated from its test construction. Select only after target correctness, repeated wall-time, memory and official practice checks.
