# Track A: Ingest

This C++17 implementation splits the regular input file at complete-line boundaries into three shards. Each worker parses its own endpoint/hour groups, preserving all uint32 latencies and error counts. The groups are merged after the workers join, exact nearest-rank percentiles are selected, and buffered output is written in the specified hour and bytewise endpoint order. It uses only the standard library. The offline Docker build uses the pinned allowlisted GCC image and `-pthread`.

On a shared native x86 dot VM, the previous insertion-based three-shard version's full-data median was 0.200 s versus 0.386 s for the prior selected implementation, with process RSS 36.0 versus 25.2 MiB. Using the pinned formatter and scc versions on temporary copies produced 226 versus 127 code lines including the Dockerfile; the measured time, RSS and source factors imply approximately 1.187× K before dependency effects. This is not an official board score or cgroup result. The prior selected code remains at `experiments/a-serial-f45.cpp`.

The candidate matched the published full-data hash in the restricted ARM Linux Docker check and passed alternate reference samples, synthetic inputs, 1 MiB chunk boundaries and exact shard-boundary placements. From the repository root, `python3 experiments/a-shard-boundaries.py /path/to/compiled-binary 3` reruns the shard checks.

The previous insertion-based merge emitted a GCC 14 `-Wstringop-overflow` warning. Review found its source and destination disjoint and bounded by 3.1 million lines, and sanitizers found no defect; this suggests, but does not prove, a compiler false positive. The selected merge checks the combined size explicitly, then resizes and copies; it compiles without that warning. On the shared x86 VM it measured 0.2124 s / 36.07 MiB versus 0.2161 s / 35.84 MiB for the insertion version. Pinned formatted code counts were 233 versus 226 lines including Dockerfile; the estimated coefficient ratio is 1.0028, too close to call under VM noise. See `experiments/dot-vm.md` and `experiments/static-a-checked/`.

Obtain real board time, cgroup memory and run IDs before claiming a score.
