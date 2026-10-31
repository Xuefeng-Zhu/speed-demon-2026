# D query-phase screens at 804a03c (none selected)

The baseline is `track-d/src/main.rs` at `804a03c`: coarse radix keys plus the next-two-pops prefetch. Each `make_*.py SRC OUT [ARG]` script writes one variant. Every variant matched the full seed-1 SHA-256. Timings are alternating full-seed runs on the 8-thread sandbox (Xeon 8488C, 105 MB L3), wall median / min in ms; they are not board numbers. Same-batch baselines drift between about 173 and 177 ms, so differences of 1–2 ms are noise.

## Where query time goes

`cyc3.rs` adds `rdtsc` timers to the search loop, kept thread-local and flushed once per query. A first version with shared atomic counters inflated the total by 50% and was discarded. Over three runs the shares of query-loop cycles were:

| Section | Share |
|---|---:|
| relaxing the popped node's edges | 44–45% |
| `top()` on both queues | 16% |
| `get(u)` for the popped node | 14% |
| choosing a side and popping | 13% |
| next-pop prefetch | 12% |

`dup.rs` counts expansions. There were 7,598,815 expansions over 22.4M edges. Of these, 247,000 (3.3%, 0.79M edges) repeated a node at the same distance, coming from duplicate entries within one coarse bucket, and 4,474 re-expanded a node at an improved distance. Deduplication could save at most about 3% of relaxations.

## Screens

| Variant | Script | Runs | Baseline | Variant |
|---|---|---:|---:|---:|
| `SHIFT` 5 | `make_q.py … s5` | 15 | 173.5 / 167.3 | 173.8 / 168.0 |
| `SHIFT` 7 | `make_q.py … s7` | 15 | 173.5 / 167.3 | 178.9 / 172.1 |
| Prefetch bounds 3 ahead, row 1 ahead | `make_q.py … pf31` | 15 | 173.5 / 167.3 | 170.9 / 165.1 |
| Prefetch 4 / 2 ahead | `make_q.py … pf42` | 31 | 175.7 / 169.7 | 175.1 / 165.7 |
| Prefetch 4 / 3 ahead | `make_q.py … pf43` | 31 | 175.7 / 169.7 | 174.6 / 169.7 |
| Ring bucket queue (64 / 256 / 1024 slots) plus binary heap for far keys, replacing the radix heap | `make_ring.py … R` | 15 | 174.0 / 170.4 | 179.3 / 177.3 / 178.9 |
| Heap entries carry the stored distance, so no `get(u)` on pop | `make_entryd.py` | 21 | 173.3 / 168.1 | 173.0 / 166.7 |
| Expand one side 8 / 16 times before re-comparing sizes | `make_batch.py … N` | 31 | 176.1 / 169.2 | 175.2 / 168.1 and 173.9 / 168.4 |

`make_entryd.py` keeps answers exact because every queued distance is a real path length; stale entries are re-expanded instead of skipped. Side batching does not affect correctness, because any expansion order is valid and the loop still stops when either queue is empty. Its 1.2% gain at 16 is within batch-to-batch noise and would add about 6 lines.

## Node ordering

`make_marks.py` prints the query-phase time alone. Five runs each, query phase in ms:

| Ordering | Query phase |
|---|---:|
| current (parallel clusters of up to 1,024) | 82.8–87.8 |
| single-threaded clusters of 1,024 | 83.9–88.7 |
| clusters of up to 65,536 | 82.6–90.2 |
| one BFS over the whole graph (single-threaded) | 85.2–89.6 |

All orderings give the same query time. Locality from renumbering is saturated, so a better ordering will not shorten the queries.

## Conclusion

At about 85 ms in this sandbox, the query phase is close to the floor for bidirectional label-correcting search on this machine. The remaining costs are the relaxation loop and queue bookkeeping, and none of these screens reduced them reliably. A larger query-phase gain would need fewer expanded nodes, for example goal direction or shortcuts. The earlier landmark and contraction experiments found their preprocessing too expensive, because one full-graph Dijkstra costs about as much as a fifth of all queries combined.
