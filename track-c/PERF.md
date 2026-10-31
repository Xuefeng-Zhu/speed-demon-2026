# Track C: performance log

Every step from the reference to the current version. **Board run IDs are still to be added**: every number below was measured locally, on a shared 2-vCPU arm64 VM that other jobs were also using, so wall times there vary by about 2x from run to run. The local numbers show direction only. The board numbers are the ones that count.

- "Wall" and "CPU" are the best of 3 to 5 runs on seed 1 `full` (3,320,000 records, 202 MB).
- "Heap" is the polled peak `RssAnon`, which is what the harness's cgroup `memory.peak` charges. Mapped page-cache pages are not charged to the run.

| Step | Change | Run ID | Wall (s) | CPU (s) | Heap (MB) | Hash |
|---|---|---|---|---|---|---|
| 0 | The reference, unchanged. Board: 14.44 s, 367 MB | (board) | 27.9 | 16.2 | 347 | ok |
| 1 | Rust, std only: `mmap`, two-pass quote-parity split across threads, a hand-written parser, per-thread aggregates. Distinct names in 64 mutex shards keyed by slices of the mapped file, plus one global atomic group×name bitset | pending | 1.9 | 1.9 | 9.6 | ok (after fix below) |
| 2 | Copy names into `Box<[u8]>` keys. Per-shard row bitsets that count a distinct name when they first set its bit, so no global id counter and no final popcount. 256 shards, each aligned to 128 bytes | pending | 5.0 | 2.4 | 12.7 | ok |
| 3 | Fix step 2's shard index (see failed experiments): shard on hash bits 32–39 | pending | 1.0 | 1.8 | 12.6 | ok |
| 4 | Restructure for size: one `merge` for records and threads, `par` helper, unified `field`. 241 → 154 code lines after rustfmt | pending | 0.97 | 1.67 | 12.6 | ok |

`sample` with the current version: 0.17–0.35 s wall and 12.4 MB heap, against the reference's 2.8 s and 66 MB.

## Failed experiments and bugs

- **Skipped the first record (bug, caught by the hash).** Chunk 0 also went through `sync`, which skips to the end of the first LF and so dropped record 1. Chunk 0 now starts right after the header.
- **Shard index from the top hash bits.** With `hash >> 56` picking the shard, every key in a shard shared hashbrown's 7-bit control tag, which is also taken from the top bits. Every probe then matched and fell through to a full key comparison. That ran about 2.5x slower than step 3. Moving the shard index to bits 32–39 fixed it.
- **Keys pointing into the mapped file (step 1).** These save the `Box` copies, about 3 MB of heap, but every lookup compares against a random spot in a 200 MB file, which means a cache miss and often a TLB miss. Step 3's boxed keys were clearly faster.
- **Group bitset stored inline as `[u64; 4]` in the map value.** This removes the row lookup, but 48-byte buckets made the table bigger and it measured no faster. It would also cap the number of groups at 256. Dropped.
- **SipHash (`std` default) instead of the Fx-style hasher.** About 15% more CPU, so the 13-line hasher stays.
