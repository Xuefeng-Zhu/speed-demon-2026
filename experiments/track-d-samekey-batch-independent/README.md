# Independent review of bounded same-key batches

Reviewed `../track-d-samekey-batch/batch8.rs`, SHA-256 `29ea939a98403eb407d07ae1e3ec5a1cdec7a3546b1be8f154dbfd565fcd4db1`. This is a correctness review of an unselected experiment, not a performance result.

The active radix heap's zero bucket holds only entries with its materialized minimum key. An edge of zero weight may add more entries of the same key. The loop processes at most eight pops before rechecking side selection and the bidirectional termination bound. Each non-stale pop is a valid per-side Dijkstra expansion; delaying the check can do extra work but does not invalidate an upper bound assembled from real paths. The opposite heap cannot change during a batch. Stale entries are skipped and `reach` requires a strict distance improvement, so zero-weight cycles do not indefinitely enqueue equal distances. Existing graph-size, weight-overflow and baseline stopping assumptions remain in force.

`python3 experiments/track-d-samekey-batch-independent/oracle.py` compiled a temporary instrumented copy with overflow and debug checks and passed 109 graphs and 14,938 independent Dijkstra answers. Fixtures include zero-weight stars and cycles around the batch boundary (7/8/9 and 15/16/17), duplicate and stale paths, 100 randomized directed multigraphs and maximum u32 weights. The atomic instrumentation verified 112,165 second-or-later pops within a batch; it perturbs timing and is not performance evidence. The temporary generated data were removed automatically.

These tests and reasoning do not prove all possible graphs, and do not establish target x86 speed, full public-seed results, holdout correctness or official cgroup memory. No Mac Docker was used.

The same reasoning applies to a batch limit of 16. `oracle16.py` ran against exact `batch16.rs` SHA-256 `e435dd6c495dc0f72532ccab948a2d1e33a7a8395883a69befe11b062fb3fabc`, with explicit fixtures around 15/16/17 and 31/32/33. It passed 112 graphs and 18,012 independent answers with 235,273 observed second-or-later same-batch pops in a debug/overflow instrumented build. Instrumentation is solely evidence of exercised branches, not timing evidence.
