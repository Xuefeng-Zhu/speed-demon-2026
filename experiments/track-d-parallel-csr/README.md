# Track D concurrent forward/backward CSR builds (not selected)

The candidate runs the existing forward and backward `build_csr` stages concurrently rather than sequentially. Both are built directly from disjoint input buckets and graph output buffers; input parsing and per-query shortest-path search are unchanged. Each build currently spawns its normal number of block workers, so a 12-thread configuration can create 24 simultaneous build workers. The source is isolated from the selected track.

Five randomized paired native Mac full seed-1 runs after warmup all matched the published output hash. Candidate median wall was 0.4810 s versus 0.4072 s baseline, median CPU 2.1007 versus 2.0657 s, peak process RSS 537,608,192 versus 533,938,176 bytes. Measurements were taken on a shared ARM machine, with wide variation and other agent work active; they are neither target x86 performance nor official cgroup memory. No selection or additional correctness claims are made.

For reproduction, copy `candidate.rs` to `meeting.rs` in a temporary directory alongside `baseline.rs` and `compare.py`, then run `python3 compare.py --data /path/to/full-d --build-dir /tmp/d-concurrent-build --report /tmp/d-concurrent.json --runs 5`. The comparator compiles both with identical release flags, checks every full output hash, and reports per-process wall/CPU/RSS. No Docker was used.
