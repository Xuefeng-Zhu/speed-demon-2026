# Independent low-32 event model

`run.py` verifies candidate SHA-256 `5447d5c7d77e616b60c843c20f58cacc6bd152e6c9337e1a417f7b1768d863aa`, appends `tail.rs` to a temporary copy, and compiles it with overflow checks and debug assertions. Native ARM execution passed one test comprising 1,920,000 event operations. No selected code is changed.

The test encodes 1,027 distinct names, including empty, escaped-quote, trailing-space, 65,535-byte and 65,536-byte names, as input records. It reconstructs each from the actual 12-byte event type, routes the event by the full 64-bit hash into 1, 3, or 12 owners, and checks each distinct-name/group result against an independent HashSet. Four hash modes cover actual name hashes, a forced shared hash, distinct full hashes with identical low 32 bits spread among owners, and groups of equal fingerprints sharing cache slots and triggering promotion. It checks 257 groups and duplicates after insertion.

Synthetic hashes test the routing and collision machinery rather than the hash function itself. The test does not establish x86 SIMD correctness, real >4 GiB parsing, full cgroup memory bounds, or performance.
