# Track A: Ingest

This Rust standard-library solution maps the input, partitions it at line boundaries, and parses independent chunks into per-hour packed records. All workers use one shared, append-only endpoint dictionary. Each slot publishes its immutable hash, length, dense ID and copied name through `OnceLock`; every lookup checks exact endpoint bytes. Names remain valid when parsed input pages are released.

After parsing, the workers build a byte-sorted view borrowing the shared names, then group each hour's latencies by endpoint. AVX2 rank counting handles small groups and selection handles larger groups, preserving exact nearest-rank percentiles, duplicates and uint32 extremes. The main thread writes completed hours in order to `/out/summary.txt`. `/data/requests.log` is read-only. `SD_DATA`, `SD_OUT`, and `SD_THREADS` are optional local-test overrides.

The only dependencies are Rust's standard library and system C calls `mmap` and `madvise`. There are no third-party runtime dependencies. The included offline Docker build uses pinned image digests.

The dictionary has 4,096 inline slots, enough to stay below half full for the specified 1,842 endpoints. Per-slot initialization serializes competing discoveries of the same key, while initialized lookups need no mutex. Names have 128-byte zero-padded storage for the bounded SIMD comparisons. The implementation keeps the original parse/summary barriers and output scheduling.

See `PERF.md` for measurement and correctness evidence; local times are not official scores. The older C++ implementation remains available as `experiments/a-three-shard-checked.cpp` when integrated into the existing project.
