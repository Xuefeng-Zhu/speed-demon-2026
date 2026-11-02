# Track A: Ingest

This Rust standard-library solution maps the input, partitions it at line boundaries, and parses independent chunks into per-hour records. Endpoint hashes are checked against exact bytes before merging. The same threads then group each hour's latencies by endpoint and find the nearest-rank percentiles (AVX2 rank counting for small groups, selection for larger ones). Hours are written in order. It emits the required `/out/summary.txt`; `/data/requests.log` is read-only. `SD_DATA`, `SD_OUT`, and `SD_THREADS` are optional local-test overrides.

The only dependencies are Rust's standard library and system C calls `mmap` and `madvise`. There are no third-party runtime dependencies. The included offline Docker build uses pinned image digests.

All requested workers parse their input chunks. After both barriers, one worker exits when there is more than one, leaving N−1 summary workers alongside the main writer. A single-worker run keeps its summary worker. The writer returns fully written buffers to a shared pool holding at most four idle buffers; workers allocate immediately on a pool miss. Pending hours and output ordering are unchanged. This is an idle-buffer count limit, not a bound on all output memory.

See `PERF.md` for measurement and correctness evidence; local times are not official scores. The older C++ implementation remains available as `experiments/a-three-shard-checked.cpp` when integrated into the existing project.
