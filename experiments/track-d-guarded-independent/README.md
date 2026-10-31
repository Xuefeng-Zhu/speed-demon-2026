# Independent guarded D loader review

This test instruments a temporary copy of `../track-d-guarded-loader/candidate.rs`,
SHA-256 `77f764359aa3189f73e37d2b411ba80a700ee66ee25a40c0286e658ab45f52d4`.
It never alters the candidate or selected source. The loader is an isolated,
unselected experiment.

`python3 experiments/track-d-guarded-independent/run.py` builds optimized
overflow/debug-checked tests for normal, budget 0/1 and per-bucket logical cap
0/1. Each build checks 480 combinations of graph sizes, empty or skewed
partitions, weights 0/1/2046/2047/`u32::MAX`, and 1/2/3/7/12 threads. It
compares independently constructed forward and reverse CSR edge multisets,
checks that all fast worker closures have exited before exact retry, records
fast/retry paths and the loader ledger, and asserts neither fast nor exact
bucket capacities change during scatter. The test-only counters do not measure
allocator retention or cgroup memory. `parsed` is dropped before the retry by
Rust return/ownership semantics; its allocation lifetime is not dynamically
instrumented by this test.

The initial 2,400-case run passed: normal had 451 fast and 29 retries;
budget 0 and 1 each had 480 retries; cap 0 had 60 fast cases (empty graphs)
and 420 retries; cap 1 had 184 fast and 296 retries. All output multisets,
no-growth and joined-worker assertions passed. A subsequent revision added
explicit budget/cap rejection and cancellation counters; all 2,400 cases
passed again under an exclusive CPU window. It observed 126 cancellation
returns in normal, 1,920 for each budget variant, 1,459 for cap 0 and 971 for
cap 1. Expected budget and cap failures were observed. Those cancellation
counts describe one scheduling run, not a scheduling guarantee. No Mac Docker
was used.

## Static review

Each parser uses the same immutable byte range and `block` mapping as the
unmodified loader. It verifies both destination lengths are below the fixed
logical cap before inserting either directed tuple, so a successful fast
result contains both versions of every parsed edge. Every allocation request
first reserves its requested byte count against a shared atomic ledger; any
budget refusal or `try_reserve_exact` failure returns `None`. If returned
capacity exceeds the request, its excess is charged afterward and a refusal
also returns `None`. The ledger is deliberately cumulative, even if an earlier
buffer has already been dropped, so it can cause a conservative retry.

A failed worker sets `cancelled`; relaxed cancellation reads are only an
early-exit hint. Regardless of what another worker observes, every scoped
handle is joined and an actual `None` causes the entire `parsed` result to be
dropped before `load_graph_fast` returns. Only then can the caller invoke the
exact two-pass loader. No CSR is built from partial buckets. If no worker
fails, the existing forward/reverse CSR builder receives the complete buckets.
`Vec::try_reserve_exact` provides at least the requested capacity and each fast
push is checked against the requested logical cap, so successful fast buckets
need not grow.

This is an application-level requested/returned-capacity control, **not a
strict 320 MiB allocation or parent-cgroup bound**. Allocator excess is known
only after an allocation, so a transient footprint may exceed the ledger
before an excess charge fails. Allocator-retained memory, metadata outside the
ledger, the exact retry, CSR, thread stacks, file cache, runtime and kernel
charges are additional. `try_reserve_exact` failure causes a retry; it cannot
catch an OOM kill while subsequently touching overcommitted pages. The exact
loader's size assumptions and I/O failure behavior are inherited from the
prior implementation. This static audit and finite tests do not establish a
formal 8 GiB parent-cgroup guarantee.
