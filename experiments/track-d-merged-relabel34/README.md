# D merged renumber/relabel (rejected)

Baseline: `track-d/src/main.rs` at `963a9e5` (coarse radix keys). Today the forward rows are copied into new-id order during the clustering BFS, with heads still in old ids. `relabel` then rewrites every head in place, counting in-degrees with atomic adds, and finally scatters the backward graph. Both variants drop the in-place rewrite. The BFS only reserves ids and edge slots, and a second pass copies each row with its heads already renamed while counting in-degrees.

- `old-order.rs`: the second pass walks old ids, so `g` is read in order and the rows are written to scattered destinations.
- `new-order.rs`: the BFS also records each new id's old id (7 MB more), and the second pass walks new ids, so writes are in order and reads from `g` are scattered.

Both matched the full seed-1 SHA-256. `bench.py` ran 21 alternating runs on the 8-core sandbox (not the scoring box):

| Variant | Median | Min | Baseline median in the same batch |
|---|---:|---:|---:|
| old-order | 196.8 ms | 187.8 ms | 187.4 ms |
| new-order | 195.2 ms | 185.8 ms | 187.1 ms |

Both are about 5% slower and use more memory, because the backward first-array, or the old-id map, is live at the same time as `g`. A likely reason, not profiled: the current design copies each cluster's rows while the BFS has them in cache, and its in-degree atomics go to nearby new ids. The second pass loses one or both of those advantages. Not selected.
