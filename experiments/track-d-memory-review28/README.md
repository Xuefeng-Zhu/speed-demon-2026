# Track D coarse-bucket memory review

Read-only review of selected `track-d/src/main.rs`, SHA-256 `2a2a325a1c87e4bc68c260e0d80353e0b8f1f9a7b5be81b1ffeaaede6d813f9d`, against the published full-scale limits: 1,740,512 vertices, 5,000,000 directed edges, 2,000 queries and at most 12 workers. This is allocation accounting, **not a proof that the parent cgroup stays below 8 GiB**. No selected code, system settings, cgroup mounts or Docker were changed.

## Search payload

Each worker retains its narrow search and can lazily allocate and retain its exact wide search after fallback. Counting all 12 workers with both states, the requested element payloads are:

| Allocation | Bytes across 12 workers |
| --- | ---: |
| Narrow distance pairs, 8 bytes per vertex | 167,089,152 |
| Narrow touched indices, 4 bytes per vertex | 83,544,576 |
| Two 65,536-node narrow pools, 16 bytes per node | 25,165,824 |
| Wide distance pairs, 16 bytes per vertex | 334,178,304 |
| Wide touched indices, 4 bytes per vertex | 83,544,576 |
| Two indexed wide-heap link arrays, 8 bytes per vertex each | 334,178,304 |
| **Total requested search payload** | **1,027,700,736** |

The touched condition inserts a vertex at most once per query before cleanup, so each touched vector's preallocated `n` entries suffice. A narrow pool never pushes beyond 65,536 nodes: exhaustion cleans the partial state and reruns the query with indexed wide heaps. Each wide heap has one fixed link entry per vertex. Coarse ordering may change the number of expansions and how often fallback occurs, but not these logical capacity bounds. These figures omit allocator rounding and metadata, heap headers, thread stacks and kernel charges.

## Loader, graph and files

Both CSR graphs use two `u32` edge arrays under the official `n <= 2^21` bound, plus their row offsets. Requested CSR element payload is `2 * (8*m + 4*(n+1)) = 93,924,104` bytes. One full pass of per-block cursor copies adds `4*n = 6,962,048` bytes; counting both forward and backward passes together gives 13,924,096 bytes even though they execute in sequence.

An edge line is at most 27 bytes (two 7-digit vertex IDs, one 10-digit weight and three separators), and its header at most 16 bytes: `graph.txt <= 135,000,016` bytes. The 12 overlapping positioned-read buffers together request at most the file length plus `12*33`, or 135,000,412 bytes. Counting a separate full file-cache copy yields 270,000,428 bytes before page rounding and kernel metadata. The file cache is prewarmed outside the run, but its precise cgroup charge is not established here. Query text is at most 32,000 bytes. The largest possible shortest distance is `(n-1)*(2^32-1) = 7,475,437,821,587,745`, so the 2,000 output lines occupy at most 34,000 bytes; vector/string capacities and output-cache pages require additional accounting.

The loader initially reserves 288 edge vectors at 12 workers, each with `c = floor(floor(m/12)/12)*9/8 + 64 = 39,126` tuples of 12 bytes. **Assuming** geometric doubling, no allocator-reported excess capacity, and requested old/new payloads bounded by the geometric allocation history, final combined vector capacity is at most `12*(288*c + 4*m) = 375,219,456` bytes. Counting less than twice that, 750,438,912 bytes, conservatively covers the whole vector growth history under those assumptions. Rust's `Vec` interface does not promise this allocator behavior or an upper bound on actual charged allocator pages.

## Conditional envelope and limits

Adding all requested search state, that conservative cumulative loader-vector history, both CSR graphs and cursor passes, the full graph cache plus positioned buffers, four sets of 12 stacks at 2 MiB each, and an 8 MiB main stack gives **2,265,040,180 bytes** (about 2.11 GiB), before query/output capacities, allocator and runtime overhead, page tables, charged kernel memory, other files/cache and any harness or parent-cgroup processes. This sum intentionally combines phases that do not logically execute at the same time, to allow for retained pages; the 2 MiB thread-stack allowance and four-set retention must be checked against the actual runtime. The illustrative Docker command uses `--memory=8g`, i.e. 8,589,934,592 bytes, but the unspecified terms prevent subtracting the envelope from that limit as a guaranteed safety margin.

The official public-seed coarse-bucket runs recorded in `track-d/PERF.md` peaked at 467,632,128 and 438,222,848 parent-cgroup bytes. They establish those runs' measured peaks, not the holdout's worst case. A worst-case guarantee would require enforceable bounds for the actual allocator/growth and retention behavior, stack/runtime mappings, cgroup-charged file and kernel memory, and all processes charged to the measured parent, or an equivalent controlled-allocation/runtime design. The absence of a cgroup mount on the dot VM prevents a representative parent-cgroup stress measurement there; no mount or privilege workaround was attempted.
