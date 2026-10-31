# Independent default-capacity pool boundary test

This test appends a Rust test module to the exact unmodified capped-hybrid candidate, verified against SHA-256 `671c639be3400209e83e080dfb54947affd30ca71dc34ec17804d24d70292d9c`. Run `python3 experiments/track-d-capped-hybrid-independent/run-pool-boundary.py`. It compiles with optimization, overflow checks, and debug assertions.

Five cycles fill the actual 65,536-node pool; verify that an additional push fails without changing the queue; pop half the nodes against a `BTreeSet` oracle; refill using the free list without extending the pool; verify another failure; and drain against the same oracle. At each stage, an independent audit checks bucket placement, list and free-list disjointness, cycles, orphans and count. Each cycle uses different vertices on refill, and `clear()` is checked after the final cycle. This extends the prior randomized property test, which did not reach the real pool capacity.

Result: **1 passed, 0 failed** on native macOS ARM. This directly tests the default FastHeap capacity and bookkeeping; it does not itself exercise full-graph fallback, prove all concurrent schedules, establish x86 behavior or prove the cgroup memory bound.
