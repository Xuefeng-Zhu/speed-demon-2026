# Track A: Ingest

This Rust standard-library solution maps the input, partitions it at line boundaries, and parses independent chunks into per-hour records. On x86-64-v3 it hashes endpoint words with CRC32C while retaining exact byte comparison; if a fast shard exceeds its probe limit, that whole shard is discarded and reparsed with the original hash. Successful shards rebuild canonical endpoint hashes in original ID order before merging. Workers then group latencies by endpoint and select nearest-rank percentiles. Hours are written in order. It emits the required `/out/summary.txt`; `/data/requests.log` is read-only. `SD_DATA`, `SD_OUT`, and `SD_THREADS` are optional local-test overrides.

The only dependencies are Rust's standard library and system C calls `mmap` and `madvise`. There are no third-party runtime dependencies. The included offline Docker build uses pinned image digests.

See `PERF.md` for measurement and correctness evidence; local times are not official scores. The older C++ implementation remains available as `experiments/a-three-shard-checked.cpp` when integrated into the existing project.
