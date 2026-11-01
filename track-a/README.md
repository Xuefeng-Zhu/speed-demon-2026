# Track A: Ingest

This Rust standard-library solution maps the input, partitions it at line boundaries into chunks of about 512 KiB, and parses them, in file order, into per-hour records. Endpoint hashes are checked against exact bytes before merging. The log is nearly in time order, so an hour is closed once every chunk up to a record two hours later is parsed. The same threads then group each closed hour's latencies by endpoint, find the nearest-rank percentiles (AVX2 rank counting for small groups, selection for larger ones) and write the hours in order while later chunks are parsed, so only a few hours of records are in memory at a time. If a record arrives for an hour that is already closed, the run starts over without closing hours early, so any line order gives the right output. It emits the required `/out/summary.txt`; `/data/requests.log` is read-only. `SD_DATA`, `SD_OUT`, and `SD_THREADS` are optional local-test overrides.

The only dependencies are Rust's standard library and system C calls `mmap` and `madvise`. There are no third-party runtime dependencies. The included offline Docker build uses pinned image digests.

See `PERF.md` for measurement and correctness evidence; local times are not official scores. The older C++ implementation remains available as `experiments/a-three-shard-checked.cpp` when integrated into the existing project.
