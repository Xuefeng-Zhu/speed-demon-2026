# D 12-byte packed radix heap entries (not selected)

`baseline.rs` is the selected balanced-frontier radix-heap source; `meeting.rs` changes each heap bucket item from aligned `(u64, u32)` (16 bytes) to `#[repr(C, packed)]` `{ key: u64, node: u32 }` (12 bytes). Fields are read by value; no unaligned references are formed. All search semantics and the heap-size side choice are unchanged.

Both builds passed 80 random directed graphs (16,000 Dijkstra oracle queries each) and all 4,096 directed three-node graphs with edge weights absent/0/1/u32-max (36,864 all-pairs queries each). Every full seed-1 hash including warmup matched the published hash.

Five randomized paired native macOS ARM full-data runs after warmup gave median wall **0.5800 s packed vs 0.4661 s baseline**, median CPU **1.9552 vs 1.8587 s**, and maximum native process RSS 533,970,944 vs 533,626,880 bytes. Other processes were active and samples overlap; full samples are `report.json`. Process RSS is not official cgroup memory. The variant was not selected given slower wall and CPU in this screen.

To reproduce, generate full input separately and run `python3 experiments/track-d-packed-heap-entry/compare.py --data /path/to/d-full --build-dir /tmp/d-packedheap-build --report /tmp/d-packedheap-report.json --runs 7`. Use `experiments/track-d-balanced-frontier/oracle.py` and `exhaustive.py` with both compiled binaries for correctness. No Docker was used.
