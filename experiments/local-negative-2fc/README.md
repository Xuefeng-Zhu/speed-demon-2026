# Local negative or inconclusive experiments after 2fc9110

These are isolated alternatives, not selected code. Measurements are native macOS ARM under shared load, with output hashes checked on every full-data run. They are not official board scores; cgroup memory and target CPU can change conclusions.

- A `a-stream-groups.cpp` builds each output group from worker-local vectors instead of merging them all. It was about 26.7% slower for roughly 2.7% lower observed peak RSS in five pairs. See `a-stream-iteration.md` and `a-stream-bench.json`.
- B `b-tokenhash.cpp` computes token hashes while scanning. Five paired full runs had medians 1.539 s versus 1.448 s for the bounded prototype, with similar process RSS. Hashes, edge, boundary and randomized tests passed. See `b-tokenhash-bench.json`.
- D `d-heap/` reuses heaps: five paired medians 1.25315 versus 1.26085 s, with similar maximum process RSS; no reliable gain. `d-joint/` constructs CSR differently and was slower: 1.813 versus 1.543 s. Both matched the full hash; the heap version also passed 16,000 randomized Dijkstra queries. See the corresponding JSON reports.
