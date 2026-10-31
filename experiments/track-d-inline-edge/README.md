# First-edge inline CSR (experimental, not selected)

A pre-hugepage balanced-frontier baseline and a candidate that retains full adjacency but duplicates each first edge into its indexing row. All full hashes, 16,000 random oracle queries and 36,864 exhaustive small-graph queries passed. Seven native shared ARM pairs gave median wall 0.5555 s vs 0.5324 s and CPU 1.980 vs 1.907 s; peak native RSS approximately 591 vs 534 MB. The candidate is unselected. It does not contain the selected bc902c7 hugepage hint, and these results are not target or official measurements. No Mac Docker was used.
