# Track D rolling-window priority queue experiment

Isolated negative experiment against selected `baseline.rs` (SHA-256
`1022f4d9c9956b17fd054e96a26d09551eff61936a851edf88505e12e2b1946c`).
`meeting.rs` replaces each radix heap with 4096 rolling distance buckets,
occupancy bitmaps, and an exact binary-heap overflow. It retains the balanced
frontier search; this has not been promoted or independently reviewed.

On the shared ARM Mac, seven alternating full seed-1 pairs all produced the
published hash. Median wall was 0.32568 s versus 0.26657 s baseline; median CPU
2.26725 s versus 1.85843 s; peak RSS 556,072,960 versus 535,937,024 bytes.
These are native, non-official measurements. The candidate passed 16,000
random directed-graph oracle queries and 36,864 exhaustive three-node
all-pairs queries in an optimized overflow-checked build. See `report.json`
for per-run measurements. No datasets are included.
