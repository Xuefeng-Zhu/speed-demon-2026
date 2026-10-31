# Native x86 dot VM results

Results supplied from a dot VM run against repository commit `e47b04fd28751f65cb398ece736af3375cbe5fc7`. The programs were compiled natively for x86 using GCC 14. These are local iteration results, not official board runs, Docker scores, or measured results on the competition machine. The five individual timings, exact compiler flags, VM model and memory measurements were not provided; do not infer them from these medians.

| Track | Original median | Candidate median at tested commit | Original / candidate |
|---|---:|---:|---:|
| A | 0.488 s | 0.390 s | 1.25× |
| B | 6.826 s | 5.666 s | 1.20× |
| C | 4.072 s | 0.970 s | 4.20× |

Each median represents five native runs on the full seed-1 data. The outputs for A, B and C matched their published full-data SHA-256 hashes. Nine small differential cases passed, along with Track A boundary and synthetic tests. Track D was not part of this initial VM run because Rust was unavailable; see the later follow-up below. These checks do not establish correctness on the private holdout or official scores.

## Track D follow-up

After Rust was installed on the dot VM, the selected six-worker candidate was built with `rustc 1.99.1`. It matched three small differential seeds and the published full seed-1 output SHA-256 `a23dbdf0a3e49cc8901310a9ee1dc6a9a569a85297b6da75c2a7002cb2ed277e`. A reconstructed twelve-worker variant was compared with it using native five-run medians:

| Configuration | Wall time | Peak RSS |
|---|---:|---:|
| Six workers, selected | 2.321 s | 357.2 MiB |
| Twelve workers, reconstructed | 2.195 s | 597.2 MiB |

Using the published time and memory exponents, the ratio of six-worker K to twelve-worker K is approximately `(2.195 / 2.321)^0.50 × (597.2 / 357.2)^0.20 = 1.078`, assuming the source-size and dependency factors are equal and the memory cap does not bind. Thus, on these local figures, the six-worker choice is favored by about 7.8% on K. This is only an estimate: the official harness uses a trimmed mean for time and the highest cgroup memory peak, not necessarily these VM medians and process RSS; machine, CPU pinning, memory accounting, and unseen holdout can differ. No official run IDs or scores exist yet. Retain six workers provisionally and compare on the board.


## Track C parallel follow-up

On a shared native x86 dot VM using GCC 14, the parallel country-sort experiment from commit `33e4c8f3d3794d94b08125c9485c92ced1e9993f` and the serial candidate matched the full seed-1 hash and alternate-reference cases. The five-run median wall times were 0.4376 s and 0.9685 s respectively (2.21×); maximum process RSS was 269276 KiB for each and median CPU times were 1.007 s and 0.968 s. Exact individual timings, compiler flags and VM model were not supplied. These are not official board or cgroup results. The experiment was promoted; the prior serial source is preserved as `experiments/c-serial.cpp`.


## Native x86 variant comparison at 9c33a3e

The dot VM compared variants from commit `9c33a3ea4d3ecd7110adece771376e2b17de1f4e`. Across the overall test campaign, all 84 full-data runs and 24 alternate-reference comparisons passed; additional A boundary/synthetic, B edge, and D randomized-oracle, epoch, and extreme tests passed. These were native shared-VM measurements, not official board or cgroup results. Individual samples and exact compiler flags were not supplied here.

- B streaming index: median 1.445 s versus 5.750 s for the then-selected version; process RSS 470 versus 337 MiB. Streaming and mmap parallel indexing were essentially tied on time, but streaming used 31.5% less RSS. The time and memory factors imply approximately 1.87× K before source-size and dependency factors; official scc and cgroup measurements remain outstanding. Streaming was promoted; its previous selected source is `experiments/b-serial.cpp`.
- D sparse: median 1.991 s versus 2.276 s for its prior dense baseline, with slightly lower process RSS (exact RSS was not supplied). Seen16: 2.144 s versus 2.318 s for its baseline with approximately 11% lower RSS. Packed: approximately 2% slower with approximately 22% lower RSS. Based on time and memory factors alone, seen16 is approximately 1.064× its baseline; sparse is approximately 1.069× before its unspecified RSS benefit. Local rustfmt line counts suggest a modest source-size penalty for both, but are not the official scc count. Sparse and seen16 are too close to rank reliably without precise matched RSS and official source counts; seen16 was selected provisionally because it makes the smaller, independently tested change. Prior dense and alternative sparse code remain available for further comparison.
- A buffered and parallel variants produced modest speed gains with higher memory; exact values were not supplied, so no K or source-size comparison is claimed. A remains unchanged.
