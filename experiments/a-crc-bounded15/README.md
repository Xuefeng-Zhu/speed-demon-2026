# Track A: bounded CRC32C endpoint lookup (draft)

This is an isolated experiment. It is not selected or pushed. `baseline.rs` is the exact selected Track A source at SHA-256 `4af40353f517f566217b0f882ec25d8002f61d211dcc479c53f8a1dd5de7ed88`. `candidate.rs` has SHA-256 `9028986cf2546dfc008cf05dfdb32648cf64b6536223b933fe820cd69deb89e9`.

The x86-64 SSE4.2 build hashes endpoint words with hardware CRC32C while retaining exact endpoint byte comparisons. If a lookup or a table rehash encounters more than 48 occupied slots, the fast parser returns without producing output; its entire partial chunk is dropped, and the original parser reparses that shard. A successful fast shard rebuilds its unique endpoint table using the original hash in original ID order before cross-shard merging. This preserves IDs embedded in normal and escaped records. Non-SSE4.2 builds use the original parser. Track A's selected cargo config requests `x86-64-v3`; rustc's target configuration reports SSE4.2 enabled for that target.

`test_restart.py` creates temporary macOS-only source copies, adjusts the anonymous mmap flag for macOS, and builds instrumented test versions with `sd_crc_sim` (original mix) or `sd_crc_constant` (all hashes collide). It does not change selected source. The script passed on native ARM with release optimizations:

- Independent `track-a-verification/test.py` synthetic oracle for baseline, simulated mix, and constant mix: 0, 1,000, 100,000, and 100,000 records each.
- The official reference for 14 page-end input sizes and 1, 2, 3, 6, 12, and 64 workers, with both simulated and constant hashes.
- Mixed-shard differential against baseline at test-only caps 0, 1, and 48 and 1, 2, 7, 12, and 32 workers. Dataset includes 2,400 common-prefix endpoints, long names, compact-record escape thresholds, and the maximum 32-bit latency. Instrumentation requires both fallback and successful fast shards in each multi-worker constant-hash run.

No x86 hardware CRC execution, full official dataset, timing, official container, or board run has been performed for this draft. These ARM results do not establish target performance or validate the intrinsic on the scoring machine. Before any promotion, independently review and test actual x86 CRC execution against reference outputs, adversarial hash collisions and page guards, all compact/escaped-ID paths, full official hashes, and paired wall-clock benchmarks on the target-like machine. Assess additional source count and any compilation warnings as well.

`linux_preflight.py` is an additional, currently unexecuted Linux x86-64 test. It requires SSE4.2, compiles the actual CRC path, checks 100,000 values against an independent bitwise CRC32C implementation, checks hashing adjacent to a `PROT_NONE` guard page, and runs the synthetic and page-end reference suites. It is a test harness, not evidence that these tests have passed on Linux. `test_restart.py` now selects the temporary anonymous mmap flag according to the host OS; its macOS behavior is unchanged from the successful run described above.

## Native x86 outcome

Parent-run shared dot VM paired full-seed tests measured 2.0–5.7% lower wall time at twelve workers; nine-worker results were mixed, and native process RSS was unchanged. An initial all-escape slowdown did not reproduce. Across the A, B and D packages, 308 full hashes, 28 alternate references, 48 all-escape runs and actual ISA/guard/fallback tests passed. These are native VM measurements, not official scoring-box or cgroup results; target practice follows after the D single-change trial.
