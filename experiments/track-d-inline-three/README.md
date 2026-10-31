# Three-inline-edge CSR (experimental, not selected)

This variant of `../track-d-inline-compact/` uses a 32-byte-aligned row and up to three inline edges, with additional edges in a compact overflow array. Baseline is the old pre-hugepage balanced-frontier D, not currently selected `bc902c7`; rebase and apply the same hugepage hint before comparing against the current selection. The five-million-edge specification keeps its packed overflow length within `u32`.

All full-seed hashes, 16,000 random queries, 36,864 exhaustive small-graph queries, maximum-size maximum-weight chain, 6,000 repeated/unreachable queries, four skewed/high-degree graphs, and `../track-d-inline-compact/independent-review.py meeting.rs` passed. This is not an independent static review of the separate 32-byte alignment change.

The initial `report.json` overlaps our own four-inline timing and is contaminated. A separate nine-pair shared ARM native repeat (`repeat.json`) had median wall 0.3440 s vs 0.3350 s baseline, CPU 1.729 vs 1.833 s, peak native RSS 573,620,224 vs 536,281,088 B; all full hashes matched. No consistent wall win and no x86 or official result have been established. No Mac Docker was used.
