# Local empty-name union (not selected)

`baseline.rs` is the selected CRLF source (SHA-256 `3e181c76981348a96b48470844ee0f8988847d32164ff935a211024861c86ad4`). `candidate.rs` accumulates empty-name group membership per worker and ORs it during output, avoiding the shared dictionary for empty names while retaining exact counting across workers. This isolated prototype was full-hash screened only; no broad correctness or independent review has been completed.

Nine and eleven randomized warm-cache paired full-seed ARM native runs all matched the published output hash. Median candidate/baseline wall was 0.18318/0.18404 s then 0.15869/0.15874 s, and CPU 0.9361/0.9559 s then 0.8281/0.8367 s. Shared host contention and differing CPU from scoring hardware make these nonofficial; the two screens do not establish a useful speed win. Native process RSS was about 226 MB for each. Reports contain individual samples. No Mac Docker was used. The candidate is not selected.
