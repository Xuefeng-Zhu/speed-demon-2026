# D query-loop prefetch, plus rejected parse screens

`baseline.rs` is `track-d/src/main.rs` at `dbab6be` (BFS prefetch). After the BFS prefetch was reverted in `b607e9e`, the selected change was re-applied on top of the revert, together with the `prefetch` helper it needs. All variants matched the full seed-1 SHA-256. Timings come from alternating full-seed runs on the 8-thread sandbox (Xeon 8488C), not the board.

Re-measured after the revert, one batch of 25 alternating runs: `b607e9e` 188.0 ms median (min 178.6); query prefetch alone, as committed, 175.3 (170.3); query prefetch plus the reverted BFS prefetch 170.6 (162.2). The committed version passed the same checked suites.

## Selected: prefetch the next two pops (`make_qpf.py SRC OUT two`)

After each pop, the search looks at the two entries it will pop next from the same side's minimum bucket, which are the last two of the `buckets[0]` stack. It prefetches the row bounds (`first`) of the second-to-last one and the adjacency row of the last one. A push or a side switch can change which node actually comes next; a wrong guess only costs a wasted prefetch. Answers are unchanged.

| Variant | Runs | Median | Min |
|---|---:|---:|---:|
| baseline | 15 | 181.5 | 171.5 |
| `first`: row bounds of the next pop | 15 | 177.3 | 168.3 |
| `two`: bounds of the 2nd next, row of the next | 15 | 172.6 | 165.4 |
| `dist`: row of the next (bounds read directly) | 15 | 174.2 | 169.3 |
| baseline | 25 | 177.2 | 172.8 |
| `two` | 25 | 169.1 | 163.5 |
| `three-stage.rs`: also the neighbours' distance slots | 25 | 181.2 | 175.3 |

The three-stage version walks the next node's row an extra time and loses. An overflow- and debug-checked build of `two` passed the random, exhaustive, threshold, 2^21 boundary, extreme and same-bucket suites (see `../track-d-coarse-radix33/README.md`).

## Rejected: parse screens (`make_parse.py SRC OUT OPTS [K]`)

The profile showed per-thread parse times of 14.4–19.7 ms on equal byte ranges. Splitting the file into `threads × K` pieces taken from an atomic counter did not help, and neither did `MAP_POPULATE` on the graph mapping. 15 runs each:

| Variant | Median | Min |
|---|---:|---:|
| baseline | 178.1 | 172.9 |
| chunks ×4 | 179.2 | 174.6 |
| chunks ×16 | 179.4 | 173.1 |
| `MAP_POPULATE` | 187.1 | 179.3 |
| chunks ×16 + `MAP_POPULATE` | 182.7 | 177.6 |
