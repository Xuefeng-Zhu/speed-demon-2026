# D renumbering-BFS prefetch, re-screened on the trimmed source

`baseline.rs` is `track-d/src/main.rs` at `97df345`: coarse keys, next-pops prefetch, line trim. The earlier three-stage BFS prefetch (`dbab6be`, see `../track-d-bfs-prefetch36/`) was reverted in `b607e9e`. Here it is re-screened in parts, so each stage's lines can be weighed against its gain now that S is counted after rustfmt.

`make_bfs.py SRC OUT V` writes variant V; the selected variant, called `row0` below, is the one-stage edit written directly. All variants matched the full seed-1 SHA-256. Timings are alternating full-seed runs on the 8-thread sandbox, wall median / min in ms, not board numbers. "Lines" is the change in formatted code lines.

| Variant | Prefetches, distance ahead in the BFS queue | Lines | 25 runs | 31 runs |
|---|---|---:|---:|---:|
| baseline | none | 0 | 171.7 / 166.4 and 172.0 / 168.2 | 174.7 / 163.3 |
| `full` | row bounds 16, row 8, heads' claim slots 4 | +12 | 167.4 / 159.1 and 168.1 / 162.6 | |
| `two` | row 8, heads' claim slots 4 | +9 | 168.2 / 156.9 and 166.6 / 160.8 | 167.7 / 162.4 |
| `claims` | heads' claim slots 4 | +6 | 172.8 / 166.9 | |
| `rows` | row bounds 16, row 8 | +7 | 168.5 / 161.8 | |
| `row` | row 8, with a `head` closure | +4 | 167.3 / 162.3 | |
| `row0` (selected) | row 8 | +3 | | 167.4 / 161.2 |

The gain comes from prefetching the row of the node eight places ahead. Prefetching the claim slots does nothing on its own, and the other stages add lines without a reliable extra gain. `full` and `two` cost more lines because rustfmt splits the claim-slot loop over three lines. `row0` measured 4.2% faster than baseline in the 31-run batch (174.7 → 167.4 ms) for 3 counted lines. By the K model that is about +2.1% from T, minus about 0.1% from S (376 → 379, board S ≈ 386).

An overflow- and debug-checked build of `row0` passed the random, exhaustive, threshold, 2^21 boundary, extreme and same-bucket suites (see `../track-d-coarse-radix33/README.md`).
