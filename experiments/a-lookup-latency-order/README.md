# Track A latency/status before table lookup (experimental)

Exact selected compact-record baseline `baseline.rs` SHA-256 `4af40353f517f566217b0f882ec25d8002f61d211dcc479c53f8a1dd5de7ed88`; candidate `candidate.rs` SHA-256 `6e3a05223619c2a753be1f4a7ea2cf2a547a128e1665718885ee6983c0d263fe`. The only change computes the existing latency and 5xx reads before, rather than after, the independent endpoint-table lookup. It changes no mapping indices, endpoint hashing/equality, record encoding, bounds or output logic. An independent review found no valid-input semantic or bounds defect: `parse_latency` and status read immutable mapped data, while `Table.find` mutates only the endpoint table.

Two randomized shared native ARM pairs at 12 workers after two warmups gave candidate/baseline median wall 0.038265/0.040833 s (11 pairs) and 0.037795/0.039950 s (15 pairs), CPU 0.178529/0.190204 s and 0.180102/0.190995 s, with roughly equal native RSS. All 60 full hashes including warmups passed. Test builds changed Linux anonymous mmap flag to Darwin only; ARM timing and process RSS are not x86, official or cgroup results. No target speedup is claimed.

The candidate passed the four-case independent oracle (empty/1k/100k/100k), 14 page-end fixtures at 1/2/3/6/12/64 workers, the 132,624-group latency grid at 1/2/6/12/64 workers, and compact stress (empty, 40k all-escape, 40k alternating, 87,192 records across 2,422 endpoints) at 1/2/3/7/12/32. A test-only all-hashes-zero candidate passed the oracle and compact stress, including table growth. Independent `independent-review.py` matched the reference for both baseline and candidate with normal and all-zero hashes at 1/2/7/12/32, covering 2,426 endpoints including every length 1–125, duplicate lines and status/latency/escape boundaries. Exact-source property tests passed 49,440 record encodings and escape ordering. A disposable 3.1M all-escape dataset produced exact output at workers 1 and 12 for both binaries; one paired observed sample is in `all-escape.json`, not a performance conclusion. No Mac Docker was used.

## Required target testing

Run from this archive root on a disposable Linux x86-64-v3 VM with no concurrent benchmark and separately generated official full seed-1 data:

```sh
for n in baseline candidate; do
  rustc --edition=2021 -O -C lto=fat -C codegen-units=1 -C panic=abort -C target-cpu=x86-64-v3 "experiments/a-lookup-latency-order/$n.rs" -o "/tmp/a-order-$n"
  python3 experiments/a-lookup-latency-order/make-forced.py --source "experiments/a-lookup-latency-order/$n.rs" --forced --output "/tmp/a-order-$n-forced.rs"
  rustc --edition=2021 -O -C lto=fat -C codegen-units=1 -C panic=abort -C target-cpu=x86-64-v3 "/tmp/a-order-$n-forced.rs" -o "/tmp/a-order-$n-forced"
done
python3 experiments/a-lookup-latency-order/run-properties.py
python3 experiments/a-lookup-latency-order/independent-review.py --baseline /tmp/a-order-baseline --candidate /tmp/a-order-candidate --forced-baseline /tmp/a-order-baseline-forced --forced-candidate /tmp/a-order-candidate-forced --reference official/reference/a_ingest.py
python3 track-a-verification/test.py --binary /tmp/a-order-candidate --io directories
python3 track-a-verification/page_end_test.py --binary /tmp/a-order-candidate --reference official/reference/a_ingest.py
python3 track-a-verification/latency_grid_test.py --binary /tmp/a-order-candidate
python3 experiments/a-compact-records/stress.py --binary /tmp/a-order-candidate --reference official/reference/a_ingest.py
python3 experiments/a-compact-records/stress.py --binary /tmp/a-order-candidate-forced --reference official/reference/a_ingest.py
python3 experiments/a-compact-records/all-escape.py --baseline /tmp/a-order-baseline --candidate /tmp/a-order-candidate --report /tmp/a-order-all-escape.json
python3 experiments/a-scheduling-lanes/compare.py --baseline /tmp/a-order-baseline --candidate /tmp/a-order-candidate --data /path/to/full-a --report /tmp/a-order-x86.json --workers 12 --runs 15 --warmups 2
```

The output-file and full hash are checked for every paired run; process RSS is not cgroup peak. Verify repeatability and official sandbox/practice before any promotion. The archive includes source, tests and official reference materials, not datasets, credentials or cached answers.
