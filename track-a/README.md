# Track A: Ingest

This candidate computes the exact per-hour, per-endpoint latency percentiles and error counts. It reads `/data/requests.log` and writes `/out/summary.txt`. It uses C++17 and the standard library only; the Docker image builds without network access from the pinned allowlisted GCC image. Set the team name in `.speed-demon.toml` before entering.

## Approach

The format fixes the timestamp width and the 72-hour date range. We derive the hour bucket from the date and hour digits, skip the method, and intern each distinct endpoint. Each endpoint has an array of 72 independent groups; every line, including duplicates and arbitrarily late lines, contributes to its group. Latencies are kept as unsigned 32-bit integers. After parsing, we order endpoints bytewise and compute exact nearest-rank percentiles. Small groups are sorted, and larger groups use selection at the three required ranks. We use integer arithmetic for error ppm.

This design keeps only one copy of each endpoint and avoids date parsing or per-record allocation, while treating the entire 72-hour period as live. It does not assume that a group is closed when a later hour arrives. The input is read in chunks, with any partial line carried to the next read, and never written; the only output is the required file. It assumes valid inputs as permitted by the specification.

Build locally with `c++ -O3 -std=c++17 -o /tmp/speed-demon-a-ingest main.cpp`, then run `/tmp/speed-demon-a-ingest /path/to/requests.log /path/to/summary.txt`. With no arguments the official `/data` and `/out` paths are used. From the workspace root, run `python3 track-a-verification/test.py` after building for independent synthetic differential tests.

With another 24 hours, tune the selection threshold and data layout on the scoring CPU, and use multiple workers only if measured gains outweigh memory and merge costs. Check the private-seed gate and document real board run IDs rather than treating local timings as official scores.
