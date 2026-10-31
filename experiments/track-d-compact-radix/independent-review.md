# Independent compact-radix review

Reviewed `meeting.rs` SHA-256 `61f93039c9519076b797debf60390d8dfd1072312ee14bfd988e91eb01004076` against `baseline.rs`. No defect was found within the official full-scale bound of 1,740,512 nodes; the performance results and promotion decision are separate.

Short entries pack a key below 2^43 into the high 43 bits and an ID below 2^21 into the low 21 bits. A short key is always less than every wide key. Nonnegative relaxations insert no key below the last popped key. If the short heap is empty and a wide key is popped, no subsequent push into that heap can be short; calling `top` on an inactive heap does not insert anything into it. Both heaps therefore preserve radix monotonicity across the transition. The combined `count` tracks pushes and pops; short redistribution leaves counts unchanged, while the wide heap maintains its own counts. `clear` resets both queues before the next query.

Range caveat: the ID bound in `push` is only a debug assertion. In a release build, a short entry whose node ID is at least 2^21 can silently collide with key bits or be decoded as a different node. The official full dataset and smaller documented scales satisfy this bound; the candidate must not be generalized to larger graph sizes without a runtime fallback or a different encoding.

Checks run:

- `python3 experiments/track-d-compact-radix/heap_stress.py` passed 150 reuse cycles of 3,000 monotone operations each against an independent `BTreeMap` multiset model. Cases include equal keys and nodes, 21-bit boundary IDs, mixed short/wide entries, repeated peeks, transitions from short to wide, and clearing nonempty heaps. Rust overflow checks were enabled.
- `python3 experiments/track-d-compact-radix/cutoff.py /tmp/d-compact-radix-build/meeting` passed 21 directed Dijkstra-oracle queries, including exact distances 2^43−1, 2^43, and 2^43+1. The compiled candidate's source hash matched the reviewed source in `report.json`.

These checks are evidence for the invariants, not a proof of every possible input. No benchmark, Docker process, or selected-source edit was performed for this review.
