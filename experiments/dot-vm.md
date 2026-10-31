# Native x86 dot VM results

Results supplied from a dot VM run against repository commit `e47b04fd28751f65cb398ece736af3375cbe5fc7`. The programs were compiled natively for x86 using GCC 14. These are local iteration results, not official board runs, Docker scores, or measured results on the competition machine. The five individual timings, exact compiler flags, VM model and memory measurements were not provided; do not infer them from these medians.

| Track | Original median | Current median | Original / current |
|---|---:|---:|---:|
| A | 0.488 s | 0.390 s | 1.25× |
| B | 6.826 s | 5.666 s | 1.20× |
| C | 4.072 s | 0.970 s | 4.20× |

Each median represents five native runs on the full seed-1 data. The outputs for A, B and C matched their published full-data SHA-256 hashes. Nine small differential cases passed, along with Track A boundary and synthetic tests. Track D was not run in this VM because Rust was unavailable; that is a tooling limitation, not a D correctness result. These checks do not establish correctness on the private holdout or official scores.
