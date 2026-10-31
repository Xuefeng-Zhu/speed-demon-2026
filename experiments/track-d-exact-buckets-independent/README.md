# Independent two-pass loader check

Run `python3 experiments/track-d-exact-buckets-independent/run.py`. It checks the exact candidate SHA-256 `e4caa9848aadb4af327ef99cd00a2e8a0454c6ce28ea226c2485a84d44330e0e`, then appends a test module to a temporary copy. The temporary copy instruments both scatter pushes to assert that a bucket has spare capacity before each push; selected code is not changed.

On native macOS ARM with optimization, debug assertions and overflow checks, **480 loader configurations passed**: node counts 1, 2, 3, 7, 31 and 64; edge counts 0 through 1,001; highly skewed and randomized endpoints; zero, inline-boundary and u32-maximum weights; and 1, 2, 3, 7 and 12 threads. The test checks both forward and reverse CSR edge multisets, offset ordering and edge totals. The cases exercise chunk boundaries and empty slices on small files.

Static review found that both passes parse the same immutable byte slice with the same bucket mapping, so allocated capacity is sufficient for the subsequent scatter. Rust `Vec::with_capacity` guarantees capacity at least the request; this test does not prove an exact allocator allocation, target x86 speed, behavior under all schedules, or a parent-cgroup memory bound.
