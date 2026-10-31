# D bounded equal-minimum batches (unselected)

Baseline `baseline.rs` is the selected packed-adjacency D implementation (SHA-256 `793d13729fe4dabe2a1ed272fef78e19567456676ed8df52c075bc4ac33ebd05`). `batch16.rs` is candidate SHA-256 `e435dd6c495dc0f72532ccab948a2d1e33a7a8395883a69befe11b062fb3fabc`. Each iteration still selects one search side after obtaining both minima and checks the original stopping bound. The candidate pops at most 16 entries from that side's zero bucket before rechecking side choice and termination. Zero-bucket entries are all at the current minimum; zero-weight edges may insert more entries there. Pop order stays monotone per side. Delaying the stopping check may do extra work, but no invalid path can become a best bound. Stale entries skip, and strict improvement prevents infinite requeueing around zero-weight cycles. Independent static review found no defect subject to the original Dijkstra proof and documented graph bounds.

On shared native ARM, the official seed-1 **sample**, not the full dataset, produced matching published hashes on every run. A randomized nine-run five-way screen found batch16 median wall 0.018618 s vs 0.020015 s baseline; a separate randomized 15-pair repeat found 0.019178 vs 0.020536 s, median CPU 0.098531 vs 0.103774 s and maximum process RSS 54,919,168 vs 55,427,072 bytes. These short sample times are not x86, full-data or official measurements. Individual observations, flags and exact source hashes are in `sample-screen.json` and `sample-repeat.json`.

The exact candidate passed overflow/debug checked independent adversarial Dijkstra tests (`../track-d-samekey-batch-independent/oracle16.py`): 112 graphs, 18,012 queries, and 235,273 measured second-or-later same-batch pops, including zero-weight cycles and stars across boundaries 15/16/17 and 31/32/33, stale duplicates, randomized directed graphs and maximum weights. Independent random Dijkstra tests passed 16,000 queries; exhaustive tests passed 4,096 small graphs and 36,864 all-pairs queries. Packed/fallback cases passed at n=2^21 and n=2^21+1 with node and u32 weight extremes. The full-size maximum-weight chain and 6,000 repeated/unreachable queries passed. No input data, outputs or credentials are included. Full official seed, x86 and official cgroup memory remain unverified.

On an x86-64-v3 Linux target with independently generated public full seed 1, run only after verifying support and without competing benchmark load:

```sh
python3 experiments/track-d-samekey-batch/screen.py --data /path/to/full-d --build-dir /tmp/d-samekey --report /tmp/d-samekey-full.json --runs 15 --names baseline batch16 --expected a23dbdf0a3e49cc8901310a9ee1dc6a9a569a85297b6da75c2a7002cb2ed277e
python3 experiments/track-d-samekey-batch-independent/oracle16.py
python3 experiments/track-d-balanced-frontier/oracle.py /tmp/d-samekey/batch16
python3 experiments/track-d-balanced-frontier/exhaustive.py /tmp/d-samekey/batch16
python3 experiments/track-d-packed32-adj/boundaries.py /tmp/d-samekey/batch16
python3 experiments/track-d-balanced-frontier/extremes.py /tmp/d-samekey/batch16
```

Repeat the paired run and check hidden-style graph cases and peak cgroup memory before selecting; note that `screen.py` reports native process RSS, not cgroup memory. The previous u32 cutoff candidate is a separate experiment and these sources do not combine the two changes.
