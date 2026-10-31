# Traverse

An independent Rust implementation using a compressed sparse row graph and its reverse. Bidirectional Dijkstra expands the smallest frontier, relaxes every directed edge, and terminates when the two minimum unsettled distances cannot improve the best path. Six workers process independent queries; per-worker 16-bit epoch-stamped arrays avoid clearing the graph-sized distance arrays on every query and reset safely before epoch reuse. Distances use 64-bit integers. No non-standard dependencies.

Build offline: `cargo build --release --offline`. The executable reads `/data/graph.txt` and `/data/queries.txt` and writes `/out/distances.txt`. `DATA_DIR` and `OUT_DIR` can override these for local checks. The container uses the official pinned build and runtime images.

Record actual live-board run IDs in PERF.md. Timings on the scoring machine determine competitiveness.
