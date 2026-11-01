# Track D: Traverse

The task, input files and exact output format are in the [spec](https://github.com/hackathon-raptors/speed-demon-2026/blob/main/specs/d-traverse.md). This solution is one Rust file, `src/main.rs`, using the standard library only.

## Approach

Everything runs inside the timed process. Nothing is precomputed, and nothing depends on the seed. There are four phases. Each runs on one thread per available CPU (12 on the scoring box).

1. **Parse.** `graph.txt` is mapped read-only. Each thread parses the lines that start in its share of the bytes. A SWAR scanner reads up to 7 digits from one 8-byte load. Each edge goes into a bucket chosen by the block of node ids its tail falls in. Thread *j* then turns block *j* into its slice of a CSR graph with a counting sort, so the build needs no atomics. An edge is one `u32`: the head in the low `bits = ⌈log2 n⌉` bits and the weight in the rest. A weight too large for the remaining bits is stored as an all-ones escape code, and its exact value goes in a sorted side list keyed by (tail, head). With `n` = 1,740,512 that leaves 11 bits. On public seed 1, 3,496 of 5,000,000 edges (0.07%) need the escape.
2. **Renumber.** The file's ids carry no locality, so nodes are renumbered. Threads grow breadth-first clusters of up to 1,024 nodes and claim nodes atomically. Each cluster takes the next run of new ids and of edge slots with one atomic add, and copies its rows while they are still in cache. The BFS prefetches the row of the node eight places ahead in its queue. Which thread wins a node changes the numbering, never an answer. In a sandbox profile, renumbering made the query phase 3.6 times faster than with the file's ids (103 ms against 370 ms).
3. **Relabel.** The forward rows' heads are rewritten to the new ids, counting in-degrees on the way. A parallel prefix sum and a scatter then build the backward CSR. The large zeroed arrays are allocated with a transparent-hugepage hint.
4. **Query.** Workers take queries from a shared counter. Each query runs a bidirectional search:
   - **Frontier choice.** The side with fewer queued entries is expanded. If one side is boxed in behind huge weights, it runs dry at once instead of the other side exploring the whole graph.
   - **Queues.** Both queues are radix heaps keyed by `distance >> 6`. Within a bucket, nodes come out in any order. Every strict improvement is queued again and expanded with its new exact distance, including improvements to nodes already expanded. A popped node whose distance has since moved to an earlier bucket is skipped.
   - **Stopping.** The search stops when the two bucket starts add up to the best meeting found. Bucket starts are lower bounds on anything not yet expanded, so no shorter path can remain. The meeting check runs whenever a relaxation improves a distance.
   - **Distance storage.** Distances are stored complemented in `u32`, so zero means "not reached". They live in blocks of 64 node ids, handed out from a per-side pool as the search reaches them. A thread's memory is therefore the footprint of its largest search, not a slot for every node.
   - **Prefetch.** After each pop, the search prefetches the row bounds and the row of the next two nodes it will pop.
   - **Wide fallback.** A distance at or above `u32::MAX` is refused and marks the search. If the answer could depend on such a distance, the query is rerun with `u64` distances. On public seed 1 this happens for 8 of 2,000 queries.

The answers are written in query order, and the process exits without freeing memory.

## Correctness

Every answer is an exact `u64` distance or `-1`. These cases are handled exactly:
- zero weights and zero-weight cycles,
- parallel edges, duplicate lines and self-loops (every edge is relaxed),
- `s == t`, including on isolated nodes,
- unreachable targets,
- distances above `u32::MAX`.

Checked against independent Dijkstra oracles:
- 16,000 random directed-graph queries with zero and maximum weights,
- all 36,864 queries over every 4,096 three-node graph,
- 46,336 dense same-bucket queries that force re-expansions,
- cutoff boundaries at `u32::MAX`, graph sizes 2^21 and 2^21 + 1 nodes, a maximum-size maximum-weight chain, and repeated and unreachable queries.

These suites run on an overflow- and debug-checked build; see `PERF.md` and the `experiments/track-d-*` folders. The full seed-1 output matches the published SHA-256.

## Dependencies

None: standard library only, `dependency_count = 0`. `mmap`, `madvise` and `mallopt` are declared directly from the C library that `std` already links. The x86 prefetch comes from `std::arch` and compiles to nothing on other targets.

## Running locally

```sh
cargo build --release
SD_DATA=/path/to/data SD_OUT=/path/to/out target/release/solution
```

`SD_DATA` and `SD_OUT` default to `/data` and `/out`.

## Results

The best official practice result so far is T=160 ms and K=24.50, at `7b43b63`. The Python reference takes 72.69 s on the scoring box. `PERF.md` logs each measured change with its board run where one was recorded, and every rejected experiment with a pointer to its folder.

## With more time

- Reuse one set of worker threads across the phases instead of spawning about 96 threads per run.
- Build the backward graph without atomics by bucketing edges by head block, as the forward build does.
- A goal-directed search would expand fewer nodes, but the landmark and contraction trials found their preprocessing too expensive for 2,000 queries.
