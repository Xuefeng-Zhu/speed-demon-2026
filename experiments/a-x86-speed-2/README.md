# Track A x86 follow-up screens (none kept)

Three isolated variants of the production `track-a/src/main.rs` at merge `128a825` (copied unchanged as `base.rs`). Each changes one thing:

- `h3.rs`: the endpoint hash also mixes the middle word (`load(s + n/2 - 4)`), as in the earlier three-word hash. On the 1,842 seed-1 names this brings full-hash collisions back from 79 down to about 2 (per the PR #4 review).
- `lanes2.rs`: each parse thread splits its chunk at a newline near the middle and advances two cursors alternately (the interleaving used by the 1BRC winner), so the work of two independent lines can overlap. Records within an hour bucket arrive in a different order; the summary does not depend on order.
- `small2.rs`: groups of one or two records get their percentiles directly (n = 1: all three equal the value; n = 2: min, max, max) instead of going through the AVX2 rank count.

Correctness: every variant passed `experiments/a-x86-speed/check.py` (full seed-1 hash at 1, 2, 3, 6, 8, 12 threads and default; `test.py`, `page_end_test.py`, `latency_grid_test.py`; sample seeds 2, 98, 999, 4242 against the official reference) and `adversarial.py` with 0 failures. Every benchmarked output matched the published hash.

## Results

Local x86 VM (8 vCPU Xeon Platinum 8488C, 4 cores x 2 hyperthreads), `experiments/a-x86-speed/bench.py`, paired median ratio candidate/base (below 1 is faster). 20 threads oversubscribes this VM and is only a regression check for the scoring box's 20 hardware threads (6P + 8E). These are not official scores.

| Variant | 8 threads | 12 threads | 20 threads | Report |
|---|---:|---:|---:|---|
| `h3` | 1.0192 | 1.0185 | 1.0089 | `screen-1.json` (41 rounds, seed 701) |
| `h3` repeat | 1.0028 | 1.0092 | | `h3-repeat.json` (61 rounds, seed 702) |
| `lanes2` | 1.0208 | 1.0137 | 1.0060 | `screen-1.json` |
| `small2` | 1.0020 | 0.9983 | 1.0062 | `screen-1.json` |

Base medians in `screen-1.json`: 29.0 ms at 8 threads, 36.0 ms at 12, 42.0 ms at 20.

## Conclusions

- The middle word costs 0.3 to 2% on seed 1, and the collisions it would remove cost about 0.0044 extra compares per record. Speed comes first, so the two-word hash stays. Collisions only cost time, never correctness, because names are always compared byte for byte.
- Interleaving two cursors is slower here, matching the earlier ARM screen (`experiments/a-two-lane-interleaved`). The out-of-order core already overlaps neighbouring lines; the second cursor adds register pressure and a second stream of cache misses.
- Handling n <= 2 directly is within noise. The summary phase is too small for small-group tweaks to matter.
- The new code is no slower at 20 threads than at 12 in relative terms, but this VM cannot show the hybrid P/E-core effect. That needs a board run.
