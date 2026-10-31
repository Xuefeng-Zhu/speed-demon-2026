# D bounded contiguous radix buckets (unselected)

`baseline.rs` is the exact selected capped hybrid (SHA-256 `671c639be3400209e83e080dfb54947affd30ca71dc34ec17804d24d70292d9c`); `candidate.rs` is `3496a3a8e06f35e5effeb162735eef44dbb0728a44d487be2a9a951e8763160a`. The only changed code is the narrow `FastHeap`. Its 33 contiguous `Vec<u64>` buckets pack a strictly-sub-`u32::MAX` key and the full `u32` vertex. Each bucket requests capacity for 65,536 entries; the entire heap still rejects insertion once its global live count reaches 65,536, invoking the original exact indexed-wide fallback. The wide search, graph, query processing and cleanup remain unchanged. `POOL_CAP=0` goes directly to fallback.

The independent static review found no concrete packing, monotone-redistribution, tie or exhaustion defect: an entry leaves radix bucket i only for a lower bucket when the minimum key in i becomes `last`, and redistribution does not alter the global live count. Every bucket's length is at most the global live count, so with the initial capacity request at least POOL_CAP, no bucket needs to grow. This depends on the existing narrow insertion guard; debug builds assert it. Actual target correctness, cgroup behavior and hidden-data performance must still be checked.

Each narrow heap requests `33 * 65,536 * 8 = 17,301,504` bytes of bucket payload, rather than the baseline's `65,536 * 16 = 1,048,576` bytes. Across 12 workers and two heaps this is 415,236,096 versus 25,165,824 bytes, an increase of 390,070,272 bytes (~372 MiB), before allocator rounding. Applying the same conditional assumptions as `../track-d-indexed-memory-bound/README.md`, its listed search+loader/cache/stacks estimate becomes about 2,655,110,452 bytes (~2.47 GiB), not a proof of parent-cgroup <8 GiB. Requested capacity is not resident RSS; allocator retention, cgroup charging and other costs require target measurement. The benchmark cannot certify all valid inputs' peak.

Two serialized native ARM 15-pair sample screens, warmup included and randomized order, produced median wall candidate/baseline `0.019349/0.020032` and `0.020325/0.022002` s; median CPU `0.098459/0.103352` and `0.105362/0.110323` s. All 64 sample hashes matched. Maximum process RSS was ~50.8 MB candidate versus ~45.0 MB baseline. Samples are short and on a shared host; these are neither full-scale x86 nor official scores or parent-cgroup peaks. `sample-a.json` and `sample-b.json` preserve exact raw observations.

The candidate passed a one-million-operation monotone queue/multiset property model, forced cap 0/1/2 cleanup, 80 random graphs/16,000 independent Dijkstra answers, all 4,096 three-node directed graphs/36,864 answers, cutoff-1/cutoff/cutoff+1/unreachable/zero/self cases, and n=2^21 and n=2^21+1 node/weight boundaries in overflow- and debug-checked builds. The separate independent reviewer supplies default-cap/all-33-bucket tests. No x86 execution, full-data hash or cgroup result is claimed here.

For Linux x86-64-v3, run the property and forced tests, both graph oracles, thresholds and boundaries, plus the independent checker. Independently generate data and verify its published hash. Then compare in serialized randomized batches (the comparator default expected hash is the public sample; pass `--expected a23dbdf0a3e49cc8901310a9ee1dc6a9a569a85297b6da75c2a7002cb2ed277e` for full):

```
python3 experiments/track-d-capped-vector-buckets/run-property.py
python3 experiments/track-d-capped-vector-buckets/run-forced.py
python3 experiments/track-d-capped-vector-buckets/compare.py --data /path/to/full-d --build-dir /tmp/d-vector --report /tmp/d-vector-a.json --expected a23dbdf0a3e49cc8901310a9ee1dc6a9a569a85297b6da75c2a7002cb2ed277e --runs 15 --seed 8317
python3 experiments/track-d-capped-vector-buckets/compare.py --data /path/to/full-d --build-dir /tmp/d-vector --report /tmp/d-vector-b.json --expected a23dbdf0a3e49cc8901310a9ee1dc6a9a569a85297b6da75c2a7002cb2ed277e --runs 15 --seed 9449
```

Run with no competing benchmarks and inspect every output hash. No Docker was run on the Mac.

Parent-run native x86 dot VM paired full-seed wall comparisons were 5.8% faster in one batch but 0.4% slower in the repeat, so no stable speed gain is established. A 12-worker fallback stress reported 931,812 KiB process RSS; this is not parent-cgroup memory and is not an 8 GiB worst-case proof. Across C and D packages, 144 full hashes, 16 alternate references and actual x86 guard/reference/oracle and natural-capacity-exhaustion correctness tests passed. The candidate remains unselected.
