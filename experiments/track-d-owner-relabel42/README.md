# D backward graph without atomic read-modify-writes

`baseline.rs` is `track-d/src/main.rs` at `c149490`. Its `relabel` renamed heads and counted in-degrees with `fetch_add`, built running sums with the two-call parallel `ends`, and scattered the backward rows with `fetch_sub`, so every edge cost two locked instructions. The candidate in `track-d/src/main.rs` gives every counter and backward row a single owner. Thread *i* owns the heads in `span(i)`, a contiguous `n / threads` range of new ids.

1. Thread *i* renames the heads of its own tails' edges. An edge whose head is in its span bumps that count with a plain load and store. An edge whose head is in span *j* goes into a list for *j* as (head, tail | weight code).
2. Owner *j* adds the edges handed to it and sums its span's counts.
3. Owner *j* turns its counts into running sums, starting from the total of the spans before it. It then places its own edges by rescanning its tails' rows, and finally the edges handed to it.

Measured on full seed 1, 6.5–6.9% of edges cross spans at 8, 12 or 24 threads, so the lists are small.

## Scripts

- `make_bwd.py SRC OUT {seqsum,loops}` writes the two simpler variants in the first table: a sequential running sum in place of `ends`, and plain nested loops in place of `flat_map` in the scatter.
- `make_owner.py` writes the first owner version. The selected source then got per-owner running sums (the "owner2" step), `edges()` in the last pass, and tuple list entries.
- `racy-bound.rs` swaps both locked instructions for plain load and store without owners. It is wrong under concurrency (4 of 30 runs gave wrong answers) and is kept only as an upper bound on the gain.
- `make_marks2.py` prints the relabel and query phase times; `make_anon.py` samples anonymous RSS by phase.

## Results (8-thread sandbox, not board numbers)

| Variant | Relabel phase, median / min (ms) | Lines |
|---|---:|---:|
| baseline | 23.67 / 22.77, 24.88 / 23.60, 23.97 / 23.25 | 379 |
| sequential sum | 23.68 / 22.70 | 372 |
| plain loops | 24.54 / 22.79 | 380 |
| racy bound (incorrect) | 14.27 / 13.21 | |
| owner, sequential sum | 21.96 / 20.83, 21.72 / 20.11 | 393 |
| owner, per-owner sums | 19.39 / 18.35 | 394 |

Whole run, alternating wall median / min (ms):

| Batch | Baseline | Candidate |
|---|---:|---:|
| 31 runs, per-owner sums | 167.8 / 163.9 | 164.1 / 160.5 |
| 31 runs, selected source | 168.3 / 157.8 | 161.0 / 155.4 |

The sequential sum alone saves 7 lines with no time change. It is not used separately, because the owner version needs per-owner sums to get its gain. The selected source has 393 formatted code lines, 14 more than baseline, which costs about 0.5% K. The 2–4% time gain is worth about 1–2% K.

Peak memory is unchanged within sampling. Peak anonymous RSS was 59–63 MB in the load and renumber phases for both versions, and process peak RSS was 150.5 against 150.3 MB. The relabel phase peak was 51–58 MB against 55–58 MB.

## Checks

- Full seed 1 matched the published SHA-256 with 1, 3, 5 and 8 CPUs.
- An overflow- and debug-checked build, pinned to 1, 3 and 8 CPUs, passed the random oracle, exhaustive three-node and same-bucket suites at each CPU count, plus the threshold, 2^21 boundary and extreme suites (see `../track-d-coarse-radix33/README.md`). A pinned CPU count changes `threads`, and so the spans and how many edges cross them. The random suite includes graphs with fewer nodes than threads, where some spans are empty.
