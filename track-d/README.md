# Track D: Traverse

The task, the input files and the exact output format are in the [spec](https://github.com/hackathon-raptors/speed-demon-2026/blob/main/specs/d-traverse.md).

## Approach

One Rust file (`src/main.rs`), standard library only, in three parallel phases.

1. **Parse.** Each thread reads its own byte range of `graph.txt` with a positioned read (`read_exact_at`), with no single-threaded copy. A line belongs to the thread whose range holds its first byte; ranges start at byte 1, so thread 0 drops the header the same way the others drop the partial line they start in. Each edge `u v w` goes into a bucket chosen by the *block* of its tail (`u * threads / n`), and its reverse `v u w` into a bucket chosen by `v`'s block.
2. **Build.** Thread *j* owns block *j*: its nodes, and the matching slices of the forward and backward CSR arrays. It counts the degrees of its nodes, takes a prefix sum, and scatters its edges into its own slice. No atomics, and every write stays inside a window a twelfth the size of the array. For graphs with at most 2^21 nodes, each edge has a 21-bit node and an 11-bit weight code in a `u32`; code 2047 reads the full weight from a per-edge side array. Larger graphs use the original packed `u64` representation. The two compact arrays together still reserve eight bytes per edge. The forward buckets are freed before the backward graph is allocated.
3. **Query.** Up to 12 threads take queries from a shared atomic counter. Each uses bidirectional label-correcting search, expanding the smaller frontier in coarse distance buckets and rechecking a conservative stopping bound after at most sixteen entries from the minimum bucket. Every retained strict improvement is re-enqueued, including improvements to nodes already expanded. A forward relaxation that cannot beat the current best against the unpruned reverse lower bound is skipped after checking any known reverse meeting. The fast search stores complemented `u32` distance pairs and uses a fixed pool of 65,536 radix-heap entries per direction. Distances at or above `u32::MAX` are not inserted. If pool capacity is exhausted, or a relevant answer may require a discarded distance, the partial state is cleared and the query is rerun using exact `u64` distances and fixed indexed radix heaps. Both search states are reused; only touched distance slots are cleared between queries.

All outputs are exact `u64` distances or `-1`, in query order. In particular, `s == t` returns zero and no weight, path length, parallel edge, duplicate or self-loop is discarded by the exact fallback. The fast and wide queue storage is bounded by the pool size and number of vertices, respectively. Whole-container cgroup memory also includes the loader, allocator, runtime and kernel charges; its worst-case 8 GiB bound is not formally established.

Input and output directories default to `/data` and `/out` and can be overridden with `SD_DATA` and `SD_OUT` for local runs.

## Dependencies

None (std only, `dependency_count = 0`).

## With another 24 hours

- Renumber nodes for locality, for example BFS order from one main-body node, so a search touches nearby memory. The question is whether a cheap parallel ordering pays for itself within one 2,000-query run.
- Software prefetch of the next heap entry's adjacency row (x86 `_mm_prefetch` in `core::arch`).
- A faster hand-written integer scanner (SWAR) if parsing ever shows up on the box profile; locally it is no longer the bottleneck.
- Measure the thread count (12 against 6) and the RSS of the per-thread distance arrays on the real box.
