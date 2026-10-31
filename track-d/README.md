# Track D: Traverse

The task, the input files and the exact output format are in the [spec](https://github.com/hackathon-raptors/speed-demon-2026/blob/main/specs/d-traverse.md).

## Approach

One Rust file (`src/main.rs`), standard library only, in three parallel phases.

1. **Parse.** Each thread reads its own byte range of `graph.txt` with a positioned read (`read_exact_at`), with no single-threaded copy. A line belongs to the thread whose range holds its first byte; ranges start at byte 1, so thread 0 drops the header the same way the others drop the partial line they start in. Each edge `u v w` goes into a bucket chosen by the *block* of its tail (`u * threads / n`), and its reverse `v u w` into a bucket chosen by `v`'s block.
2. **Build.** Thread *j* owns block *j*: its nodes, and the matching slices of the forward and backward CSR arrays. It counts the degrees of its nodes, takes a prefix sum, and scatters its edges into its own slice. No atomics, and every write stays inside a window a twelfth the size of the array. Each edge is one `u64` (`weight << 32 | head`). The forward buckets are freed before the backward graph is allocated.
3. **Query.** Threads take queries from a shared atomic counter, so the long tail (rank up to 131,071) balances itself. Each query runs a **bidirectional Dijkstra** search: forward from `s` over the forward graph and backward from `t` over the reversed graph. It expands the smaller frontier, breaking equal-size ties by smallest key, and stops when the two smallest keys add up to at least the best meeting distance seen. Each side's queue is a **radix heap**, a monotone priority queue that fits Dijkstra. Per-thread state is reused across queries. `dist[v]` keeps the forward and backward distances side by side in one cache line, stored as bitwise complements, so zero-filled memory means "unreached". The array therefore needs no initialisation, and only touched entries are cleared afterwards.

Correctness details: distances are `u64` (answers can pass 2^32 − 1); `s == t` answers 0 without a search; parallel edges, duplicate lines and self-loops need no special case. A target with no in-edges, or a source with no out-edges, empties one queue at once, so those `-1` queries cost nothing, where a forward-only search would settle the whole graph. Output is `-1` or the decimal distance, one line per query, in input order.

Input and output directories default to `/data` and `/out` and can be overridden with `SD_DATA` and `SD_OUT` for local runs.

## Dependencies

None (std only, `dependency_count = 0`).

## With another 24 hours

- Renumber nodes for locality, for example BFS order from one main-body node, so a search touches nearby memory. The question is whether a cheap parallel ordering pays for itself within one 2,000-query run.
- Software prefetch of the next heap entry's adjacency row (x86 `_mm_prefetch` in `core::arch`).
- A faster hand-written integer scanner (SWAR) if parsing ever shows up on the box profile; locally it is no longer the bottleneck.
- Measure the thread count (12 against 6) and the RSS of the per-thread distance arrays on the real box.
