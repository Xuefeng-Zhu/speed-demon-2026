# Independent mixed-query reuse check

This test appends `reuse-tail.rs` to a temporary copy of the exact capped-hybrid source SHA-256 `671c639be3400209e83e080dfb54947affd30ca71dc34ec17804d24d70292d9c`. Only the temporary copy changes the pool capacity. Run `python3 experiments/track-d-hybrid-reuse-review/run.py`.

It alternates manually verified answers for forced pool exhaustion, a u32-cutoff fallback, ordinary narrow searches, self queries, unreachable paths, zero-weight edges, cycles and weights up to u32::MAX. The same narrow and wide search states are reused throughout. After every query the test checks touched lists, distance arrays, both heap heads/counts/last keys, and the indexed-wide link state. Capacities 0, 1, 2, 7, 64 and 65,536 each perform 2,500 queries.

Native macOS ARM, optimized with overflow and debug assertions: **15,000 queries passed**. This is a small-graph deterministic test; it is not an x86 performance, large-input, concurrent-scheduling or cgroup memory proof.
