# Speed Demon 2026: team PeppaPig

Rust (standard library only) solutions for all four tracks of [Speed Demon 2026](https://speeddemon.dev). Each solution writes output byte-identical to the official Python reference. Licensed under MIT (see `LICENSE`).

| Track | Directory | Approach | Best board run (K) |
|---|---|---|---|
| A: Ingest | `track-a/` | mmap, parallel parse into packed per-hour records with a shared endpoint dictionary, then per-hour counting sort and AVX2 nearest-rank percentiles | 44.25 |
| B: Index | `track-b/` | Per-chunk tokenizing and inverted index with bitmaps, phrase and boolean answering per chunk, merged in document order; build-time PGO | 30.02 |
| C: Join | `track-c/` | Small `pread` buffers, AVX2 quote-parity record splitting, shared atomic per-region aggregates | 41.13 |
| D: Traverse | `track-d/` | Parallel CSR build with locality renumbering, bidirectional Dijkstra per query across threads | 27.13 |

Each track directory holds `src/main.rs`, its `Dockerfile`, a short `README.md` on the design and `PERF.md`, the log of official board runs (run IDs, T, M, S, K) and correctness checks.

## Layout

- `track-a/` to `track-d/`: the submitted solutions.
- `official/`: a copy of the organisers' specs, generators, references and harness checks at commit `ad1f06063a76bf94066f169e133ec0c2e1485b65`.
- `experiments/`: trial candidates, profiles and notes from the optimisation work. None of it is part of a submission.
- `check.py`: the starter's local container check. `RULES.md`: our rules audit.

## Running locally

Generate inputs with `official/generators/<track>.py`, then build and run a track, for example:

```sh
python3 official/generators/a_ingest.py --seed 1 --scale sample --out .data/a
python3 check.py a --data "$PWD/.data/a"
```

Every solution also reads `SD_DATA` and `SD_OUT` to override `/data` and `/out` when run outside a container. The solutions use x86-64 AVX2 and are built for the scoring machine (Intel i5-13500).
