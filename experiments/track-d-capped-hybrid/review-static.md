# Independent static review

Reviewed `candidate.rs` SHA-256 `671c639be3400209e83e080dfb54947affd30ca71dc34ec17804d24d70292d9c` versus original u32 candidate `5c07ea85035e37157f77c66ccd06d86cefd022cc42311aa95497f78dc4a6d451`. The review found no concrete correctness defect in the capped heap, narrow-search abort, or indexed wide fallback.

FastHeap reuses popped nodes from a free list. Its top operation relinks existing nodes without changing count; clear resets nodes, bucket heads, free list, count and last. If insertion fails after a distance update, the updated vertex has already been recorded in touched; cleanup resets it and clears both pools, and `(NONE, true)` forces a fresh indexed-wide query even if a partial best existed. The zero-cap and self-query paths are consistent. The original narrow cutoff exit condition is retained. Nonnegative weights preserve monotone radix keys. The indexed wide heap unlinks the old entry before replacing its tentative distance; a finalized vertex cannot improve under valid nonnegative weights. The worker count is capped at 12.

This static review is not an independent execution, x86 validation, concurrency proof, performance claim, or parent-cgroup memory proof. See README for subsequent tests and bounded logical allocations.
