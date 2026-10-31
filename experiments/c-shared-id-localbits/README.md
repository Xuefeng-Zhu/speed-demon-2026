# Track C shared name IDs and worker-local bits — unselected prototype

`candidate.rs` caches exact interned names per worker, allocates dense name IDs under sharded locks, records name/group membership in worker-local bitsets and reduces by row after parsing. Each direct-mapped cache hit checks the full name bytes. It is an experiment with no bounded-memory fallback: arbitrary unique-name input and increased worker counts can consume substantial memory. It has not received independent safety/collision review and must not be promoted in its current form.

All 16 full-seed executions (seven measured pairs and warmup) matched the expected hash. The noisy shared macOS ARM medians were candidate 0.317692 s and baseline 0.327590 s wall, with 1.366644 versus 0.905345 s CPU and peak native RSS about 313 versus 226 MB. Samples are in `arm-report.json`. These results do not establish a speed win and are not x86/cgroup measurements. No Mac Docker was used.
