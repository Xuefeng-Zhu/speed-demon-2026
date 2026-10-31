# Track D: performance log

Every step from the reference to your final version, each with the live-board run ID that measured it. Judges check that the run IDs exist and that each change moved the way you say it did.

Local numbers are from a shared 2-core arm64 sandbox (other jobs running, so wall times are noisy and only relative). The `user` CPU seconds are the steadier signal. All runs are seed 1, `full` (5M edges, 2,000 queries), and every step produced the expected sha256 `a23dbdf0…277e`. Board run IDs are still to be filled in from the live board.

| Step | Change | Run ID | T (s) | M (MB) | Points |
|---|---|---|---|---|---|
| 0 | The reference, unchanged | | 72.69 | 893 | 0 |
| 1 | Rust, parallel parse + atomic CSR, forward Dijkstra (BinaryHeap), parallel queries | | | | |
| 2 | Bidirectional Dijkstra over forward + reverse CSR | | | | |
| 3 | Forward/backward distances interleaved in one array | | | | |
| 4 | Block-partitioned CSR build (no atomics) | | | | |
| 5 | Radix heap replaces BinaryHeap | | | | |

## Local measurements (seed 1, full)

| Step | Wall (s) | User CPU (s) | Peak RSS (MB) | Nodes touched by searches | Notes |
|---|---|---|---|---|---|
| ref (Python) | ~73 on the box (template figure) | | 893 | | not rerun locally at full; at `sample`, 21–25 s here vs 0.3–0.5 s for step 5 |
| 1 | 6.8–8.1 | – | 151 | 28.1 M | load 0.7–1.6 s wall, queries the rest |
| 2 | 5.6–6.8 | 12.6–13.4 | 159 | 15.3 M | touched nodes almost halved |
| 3 | – | 11.0–11.6 | 159 | 15.3 M | about 15% less CPU: one cache miss per relaxation instead of two |
| 4 | 3.3–7.3 | load alone: 0.25 (was 2.4–2.9) | 181 | 15.3 M | load-only CPU dropped about 10x |
| 5 (final) | 3.3–7.3 | 5.0–6.4 | 181–199 | 15.3 M | queries need about 1.75x less CPU than with BinaryHeap |

The phase split before step 4 (one thread, load only): parsing plus degree counting about 0.6–1.2 s, the atomic scatter into the two CSR arrays about 3.5–4.5 s. The random `fetch_add` and store across 80 MB of arrays was the cost, not the text parsing.

## Experiments and decisions

- **Forward-only vs bidirectional** (step 2): measured with the same binary, by forcing it to expand only the forward side. 28.1 M touched nodes and 22.7 s user forward-only, against 15.3 M and 12.6 s bidirectional. Kept bidirectional. It also turns the "no-in-edge target" queries (which settle the whole 1.74 M-node main body forward-only) into instant `-1` answers, so no special-case check is needed.
- **Atomic CSR build** (steps 1–3, replaced): count degrees with `AtomicU32::fetch_add`, then scatter with `fetch_add` cursors. Simple, but random atomics across large arrays cost about 10x more CPU than the partitioned build. Dropped.
- **Binary heap → radix heap** (step 5): `BinaryHeap<Reverse<(u64, u32)>>` took 8.9–9.4 s user; the radix heap took 5.0–5.3 s on the same build otherwise. Kept.
- **Considered, not done:**
  - ALT landmarks: two full Dijkstras per landmark cost more than the whole 2,000-query workload saves at this query count.
  - BFS renumbering for locality: a sequential pass over 1.74 M nodes and 5 M edges is too close to the parallel query time to be a clear win. Listed in README as next work.
