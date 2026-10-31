# Synthetic D fallback and queue-exhaustion stress

These fixtures investigate memory and fallback behavior; **they are not the
official generator's graph or query distribution** and do not prove that any
official holdout exceeds (or stays below) 8 GiB. The default dimensions match
the official full scale: 1,740,512 nodes, 5,000,000 directed edges and 2,000
queries. The first 12 queries are identical nontrivial queries; the rest are
self-queries. A 12-worker run can therefore exercise multiple concurrent
fallbacks, but scheduling does not guarantee it. Diagnostic assertions must
confirm the actual behavior before drawing conclusions.

`generate.py` builds data inside a `TemporaryDirectory`, runs one or more
explicitly supplied binaries serially, compares every output byte with a
mathematically derived answer, and cleans up when it exits normally, raises,
or times out. An external `SIGKILL` or machine crash can leave the temporary
directory behind. Do not check generated datasets into the repository.

* `chain` has edges `u -> u+1`, weight 1 except for one central edge of weight
  `u32::MAX`, with remaining edges filled by zero-weight self-loops. Every
  nontrivial query has exact answer `u32::MAX + n - 2`. It exercises the
  numeric cutoff and can touch a large fraction of each search-state array.
* `broad` has `0 -> v -> n-1` with both weights 1 for every interior vertex,
  plus zero-weight self-loops as padding. Its nontrivial answer is 2. At full
  size, the initial frontier has more than 65,536 entries, so the candidate's
  fixed fast pool can exhaust and request an indexed-wide rerun.

The independent stress assertions are implemented by `probe.py`, which
accepts a diagnostic binary created by `instrument.py`. Instrumentation is
source-hash checked and records the maximum touched vertices in any narrow
and wide search, cutoff and pool-exhaustion query counts, wide-rerun count,
and the maximum number of simultaneous wide reruns. It adds atomics and
logging; **its timings and memory are diagnostic, not official scores**.
`wide_active_max` counts active wide reruns, including state allocation. The
touch metrics are per-search maxima, not a proof that every worker touched the
same number of pages. The diagnostic-only `SD_STRESS_THREADS` override may
oversubscribe a VM and is not in the contest candidate.

An optional `--barrier-at N` gives stronger evidence of simultaneous touches:
each worker's first wide search pauses after it has reached N distinct vertices,
and resumes only once every worker has reached that point. If a worker never
arrives, a timed barrier aborts the process with `SD_STRESS_BARRIER_TIMEOUT`
and exit code 86 rather than waiting indefinitely. `--barrier-timeout` sets
the bounded timeout in seconds (default 90, maximum 300); `--timeout` bounds
the entire direct diagnostic child and must be larger. The generator rejects
barriers with fewer heavy queries than workers or a threshold above n.
`wide_barrier_arrived` must equal the worker count for a successful barrier.
This confirms those searches had reached the threshold concurrently; it does
not prove all backing pages are resident or bound allocator, kernel, cache,
or other cgroup charges.

Compile diagnostic source and run a fast smoke test after arranging a free
native CPU window:

```sh
python3 experiments/d-hybrid-fulltouch-stress/instrument.py \
  --source experiments/track-d-capped-hybrid/candidate.rs \
  --output /tmp/sd-d-hybrid-diagnostic.rs
rustc --edition=2021 -O -C overflow-checks=yes /tmp/sd-d-hybrid-diagnostic.rs \
  -o /tmp/sd-d-hybrid-diagnostic
python3 experiments/d-hybrid-fulltouch-stress/generate.py \
  --shape chain --n 101 --m 300 --q 20 --heavy 4 --threads 2 \
  --binary /tmp/sd-d-hybrid-diagnostic \
  --probe-script experiments/d-hybrid-fulltouch-stress/probe.py \
  --require-cutoff
python3 experiments/d-hybrid-fulltouch-stress/test-timeout.py \
  --binary /tmp/sd-d-hybrid-diagnostic
```

For full-scale x86 diagnostics, run the chain and broad shapes separately;
the following use exactly 12 workers and assert the conditions actually
reached. Substitute a cgroup-measuring wrapper for the binary when measuring
the parent-cgroup peak, as described below:

```sh
python3 experiments/d-hybrid-fulltouch-stress/generate.py \
  --shape chain --threads 12 --heavy 12 --binary /tmp/sd-d-hybrid-diagnostic \
  --probe-script experiments/d-hybrid-fulltouch-stress/probe.py \
  --require-cutoff --min-wide-runs 12 --min-wide-active 12 \
  --min-narrow-touch 1740496 --min-wide-touch 1740500 \
  --barrier-at 1740500 --barrier-timeout 90 --timeout 300
python3 experiments/d-hybrid-fulltouch-stress/generate.py \
  --shape broad --threads 12 --heavy 12 --binary /tmp/sd-d-hybrid-diagnostic \
  --probe-script experiments/d-hybrid-fulltouch-stress/probe.py \
  --require-exhaustion --min-wide-runs 12 --min-wide-active 12 \
  --min-narrow-touch 65536 --min-wide-touch 1740500 \
  --barrier-at 1740500 --barrier-timeout 90 --timeout 300
```

`--barrier-at 1740500` requires all 12 workers to enter wide fallback and
reach at least 1,740,500 distinct vertices before any may leave. If a requested concurrency or touch threshold is
not reached, the probe fails: do not describe such a run as having exercised
that condition. Select thresholds from the actual experiment design rather
than assuming scheduling will make all 12 wide reruns overlap.

To compare non-instrumented binaries, omit `--probe-script` and pass
`--binary` once for each executable. Output hashes are checked; the printed
wall times are informal and do not measure cgroup memory. The probe prints
correctness and counters only: parent-cgroup `memory.peak` must be measured
separately around the diagnostic binary. A caller-owned wrapper can launch it
in a measured cgroup while forwarding `SD_DATA`, `SD_OUT`,
`SD_STRESS_THREADS`, `SD_STRESS_BARRIER_AT`,
`SD_STRESS_BARRIER_TIMEOUT_SECONDS`, and stderr so the probe can inspect the
metrics. A wrapper that launches containers or other descendants must clean
them up on termination: Python's timeout kills its direct child, not arbitrary
descendants. Native
process RSS alone does not replace cgroup accounting. Use the dot VM's
authorized Linux cgroup instrumentation for memory experiments, never Docker
on the Mac. Remove only the generated temporary dataset after abnormal
termination; do not remove pre-existing data. No actual full-scale or cgroup
result is asserted by this file.

Local diagnostic validation: the 101-node chain with 12 workers reached the
100-vertex barrier on every worker and passed 24 exact answers; a 66,000-node
broad graph caused two actual pool exhaustions, reached the 65,999-vertex
barrier on both workers and passed both exact answers. The missing-participant
test exited 86 with its timeout message. These native tests are not x86,
full-scale, or cgroup measurements.
