# Track A: Ingest

This C++17 implementation splits the regular input file at complete-line boundaries into three shards. Each worker parses its own endpoint/hour groups, preserving all uint32 latencies and error counts. The groups are merged after the workers join, exact nearest-rank percentiles are selected, and buffered output is written in the specified hour and bytewise endpoint order. It uses only the standard library. The offline Docker build uses the pinned allowlisted GCC image and `-pthread`.

On a shared native x86 dot VM, the candidate's full-data median was 0.200 s versus 0.386 s for the prior selected implementation, with process RSS 36.0 versus 25.2 MiB. Using the pinned formatter and scc versions on temporary copies produced 226 versus 127 code lines including the Dockerfile; the measured time, RSS and source factors imply approximately 1.187× K before dependency effects. This is not an official board score or cgroup result. The prior selected code remains at `experiments/a-serial-f45.cpp`.

The candidate matched the published full-data hash in the restricted ARM Linux Docker check and passed alternate reference samples, synthetic inputs, 1 MiB chunk boundaries and exact shard-boundary placements. From the repository root, `python3 experiments/a-shard-boundaries.py /path/to/compiled-binary 3` reruns the shard checks.

GCC 14 emits a `-Wstringop-overflow` diagnostic in the standard-library vector insertion used to merge shard groups. Independent review found the source and destination vectors disjoint and their combined length bounded by the 3.1 million input lines; native x86 ASan/UBSan and the boundary and full-hash checks found no issue. This suggests a compiler false positive, but is not proof of a compiler defect. A checked resize-and-copy alternative that suppresses the warning and passes the local checks is saved as `experiments/a-three-shard-checked.cpp`; its x86 performance and formatted source-size effect remain unmeasured.

Obtain real board time, cgroup memory and run IDs before claiming a score.
