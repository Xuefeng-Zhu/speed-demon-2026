# Speed Demon 2026 — working rules

Sources: the [event rules and harness](https://speeddemon.dev/#rules) and the official [`speed-demon-2026` repository](https://github.com/hackathon-raptors/speed-demon-2026), inspected at commit `ad1f06063a76bf94066f169e133ec0c2e1485b65`. The track specifications are the authoritative details; this is a working summary, not a replacement for them.

## Eligibility and delivery

- The 72-hour coding window is October 30, 15:00 UTC through November 2, 15:00 UTC, 2026. All team-authored solution code must be new in this window; AI tools are permitted. No cached answers or input-identification shortcuts. Final scoring uses an unseen generator seed.
- One team of 1–4; one GitHub repository on the `speed-demon` branch with `track-a/` through `track-d/` for entered tracks. An OSI-approved license and public source within one hour after freeze are required. Overall prizes require three or more tracks; one track can compete for its highest-K prize.
- Each track folder needs a Dockerfile, README describing approach and dependencies, `.speed-demon.toml` with track, team and language, and `PERF.md`. The optimisation log should explain each measured iteration and cite actual live-board run IDs. Do not invent run IDs or present local timings as official scores. The board requires the GitHub App. It is installed on the selected private repository; team registration, publication and formal submission remain separate steps requiring authorization.
- Inputs are under `/data` read-only; write exactly the one prescribed file in `/out`, exit zero, and produce byte-identical output to the reference. Every run must pass correctness, timeout, and sandbox gates. Formatting and ordering are exact.

## Runtime and scoring

- Offline build with an allowlisted image pinned by digest, at most ten minutes and 2 GB. `COPY --from` and `RUN --mount` may use earlier stages only; no remote `ADD`, syntax directives, or cache/secret/SSH mounts. Native CPU builds run on the scoring box. Build-time training on generator output is allowed; `/data` is absent during build.
- Runtime is unprivileged uid 65534, Linux x86-64 on an i5-13500 with AVX2 but no AVX-512, 6 P-cores / 12 threads, 8 GB RAM and no swap, no network, read-only root, and 1 GB `/tmp` tmpfs. Writes to tmpfs count towards the kernel memory peak. The run is timed from program exec to exit, with the dataset pre-warmed. See [harness README](https://github.com/hackathon-raptors/speed-demon-2026/blob/ad1f06063a76bf94066f169e133ec0c2e1485b65/harness/README.md).
- Five serial runs; T is the mean of the middle three and M is the greatest of five memory peaks. One failure invalidates the track. Timeouts: A 321 s, B 564 s, C 144 s, D 727 s. Machine speed score is 65% of the total; judges award 15% code quality, 12% technique and 8% optimisation log.
- `K = (Tref/T)^0.50 × min(50, Mref/M)^0.20 × min(1, Sref/S)^0.15 × min(1, Dref/D)^0.15`. Speed score is `50 × log10(K)`, clamped to 0–100. S counts code lines after the standard formatter; D is 1 plus direct non-standard runtime dependencies. Official generator/reference copies are free only when byte-identical. Local timings are iteration evidence, not official scores.

## Track contracts and prohibited libraries

Read section 6 of each linked spec for the complete non-exhaustive ban list. General-purpose parsing, data structures and parallelism helpers are usually allowed and charged where applicable.

| Track | Input → output | Core correctness | Prohibited |
|---|---|---|---|
| [A Ingest](https://github.com/hackathon-raptors/speed-demon-2026/blob/ad1f06063a76bf94066f169e133ec0c2e1485b65/specs/a-ingest.md) | `requests.log` → `summary.txt` | Group by UTC hour and exact endpoint; nearest-rank p50/p95/p99, 5xx count and integer floor ppm; sort hour then endpoint bytes. Duplicate lines count; uint32 extremes occur. | Dataframe/analytics and SQL engines, grouped-statistics tools. |
| [B Index](https://github.com/hackathon-raptors/speed-demon-2026/blob/ad1f06063a76bf94066f169e133ec0c2e1485b65/specs/b-index.md) | `docs.txt`, `queries.txt` → `results.txt` | ASCII-byte tokenization, strictly left-to-right Boolean operators, binary NOT and adjacent-token phrases; output count, id sum and smallest ten ids. | Search engines, information-retrieval libraries, full-text database indexes or SQL used to perform search. |
| [C Join](https://github.com/hackathon-raptors/speed-demon-2026/blob/ad1f06063a76bf94066f169e133ec0c2e1485b65/specs/c-join.md) | `records.csv`, `regions.csv` → `aggregates.txt` | Preserve CSV quoting, escaped quotes, embedded newlines and record-boundary BOM rules; join unknowns to `_UNMATCHED`, count exact distinct names and bytes, use integer cents. | Dataframe, SQL/query or relational join/group-by engines, including Arrow CSV. Standalone CSV parsers are allowed. |
| [D Traverse](https://github.com/hackathon-raptors/speed-demon-2026/blob/ad1f06063a76bf94066f169e133ec0c2e1485b65/specs/d-traverse.md) | `graph.txt`, `queries.txt` → `distances.txt` | Directed shortest paths in query order; zero weights, parallel edges, duplicate queries, unreachable nodes and distances beyond uint32 are valid. | Libraries or modules that calculate shortest paths or build routing indexes; graph containers and ordinary heaps are allowed. |

The official generator supports `tiny`, `sample` and `full` at arbitrary seeds. Seed 1 full is the board dataset; the final holdout is unseen. The specs give seed-1 hashes and worked examples. Run comparisons against the official reference across scales and seeds as well as the official harness where available.
