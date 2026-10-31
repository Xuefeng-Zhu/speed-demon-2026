# D prefetch in the renumbering BFS

`baseline.rs` is `track-d/src/main.rs` at `963a9e5`. The candidate, now in `track-d/src/main.rs`, adds an x86 `_mm_prefetch` helper (a no-op elsewhere). The clustering BFS uses it on nodes already queued ahead: the row bounds 16 nodes ahead, the row 8 ahead, and the claim slots of the row's heads 4 ahead. Answers and the numbering rule are unchanged; only cache warm-up is added. `make_pf.py SRC OUT {bfs|all} A B C` writes a variant with distances A/B/C. `all` also prefetches `rank` 16 edges ahead in `relabel`'s head-renaming pass.

Motivation: `../track-d-profile35/` showed about 23 ms per thread in BFS growth, which reads random graph rows and claim slots.

## Results (8-thread sandbox, full seed 1, not board numbers)

All variants matched the full seed-1 SHA-256. 15 alternating runs each, wall median / min (ms):

| Variant | Median | Min |
|---|---:|---:|
| baseline | 189.1 | 183.3 |
| bfs 8/4/2 | 180.3 | 174.7 |
| bfs 16/8/4 | 178.7 | 174.3 |
| bfs 4/2/1 | 178.9 | 174.8 |
| all 8/4/2 | 181.5 | 173.5 |

The confirmation run, 25 alternating pairs, gave baseline 185.8 / 180.9 against bfs 16/8/4 at 178.7 / 174.9 ms. Instrumented runs put BFS growth at 15.7–17.1 ms per thread against 20.4–21.8 ms for the baseline, with the renumber phase at 25.1–26.3 against 30.4–31.4 ms. Prefetching in `relabel` gave nothing extra and was dropped.

An overflow- and debug-checked build of the candidate passed the random, exhaustive, threshold, 2^21 boundary, extreme and same-bucket suites listed in `../track-d-coarse-radix33/README.md`.

The 18 added lines cost about 0.6% K on the source-size term. The measured 4% time cut is worth about 2% K, if it holds on the box, where the smaller L3 should make prefetch matter more, not less.
