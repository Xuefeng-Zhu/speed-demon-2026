# D phase and query profile at 963a9e5 (diagnostic only)

`make_profile.py SRC OUT` writes an instrumented copy of `track-d/src/main.rs`. It adds per-phase wall, user and sys time and minor page faults (`getrusage`); per-thread start and busy time for every `parallel` call; a split of `renumber` into BFS growth, row copy and root search; and per-query time with pop, stale, relax, improve and radix-redistribution counts. Search logic is unchanged. Every instrumented run matched the full seed-1 SHA-256.

Machine: the 8-thread sandbox (Xeon 8488C, 4 cores / 8 threads, 105 MB L3). The scoring box has 12 threads and a 24 MB L3, so random-access phases are probably relatively slower there. These are not board numbers.

## Phases (median of 9 runs, ms)

| Phase | Wall | User | Sys |
|---|---:|---:|---:|
| parse + bucket | 16.7 | 101 | 17 |
| CSR build | 13.2 | 83 | 4 |
| renumber | 30.9 | 230 | 10 |
| relabel heads | 9.8 | 69 | 0 |
| in-degree sums | 1.7 | 6 | 0 |
| backward scatter | 12.9 | 81 | 0 |
| queries | 97.3 | 730 | 7 |
| write | 0.2 | 0 | 0 |
| outside `main` (exec, exit) | 4.4 | | |

Total external wall was 219 ms with instrumentation, against about 185 ms without it.

- **renumber**: per thread, BFS growth 22.5–23.1 ms, row copy 9–10 ms, root search 0.6 ms. About 26,700 clusters, averaging 65 nodes: most clusters end when their frontier runs into nodes that are already claimed, not at the 1,024 cap. A single-threaded renumber took 162–172 ms (5× slower) and gave the same query time, so the ordering quality does not depend on parallel claiming.
- **parse + bucket**: per-thread busy time ranges from 14.4 to 19.7 ms on equal byte ranges, and the bucket vectors take about 11,000 4 KiB page faults (sys 17–36 ms CPU). The `zeros()` arrays get the hugepage hint and fault far less, for example 289 faults for the backward scatter.
- **Thread start**: the last thread of a `parallel` call started up to 2.4 ms after the call (backward scatter), and 0.2–1.1 ms elsewhere.

## Queries (one run)

- 7.94M pops, 22.4M relaxations, 9.11M improvements, 0.34M stale pops, 11.0M radix redistributions, 8 exact fallbacks (0.4 ms in total).
- 94 ns per pop and 33 ns per relaxation, which suggests the searches are bound by memory latency.
- Work is concentrated: the slowest 1% / 5% / 10% / 25% of queries take 16.5% / 51.7% / 73.1% / 94.2% of query time. The 260 queries with at least 8,192 pops take about 81%.
- The 10 unreachable queries take 0.18 ms in total (at most 44 pops), because the balanced frontier stops as soon as one side runs dry.
- Cold start: the first 24 queries run at 158 ns per pop against 93 ns later, about 3 ms of CPU in total. Negligible.
- Worker balance: busy 92.4–95.5 ms against 95.6 ms wall.
