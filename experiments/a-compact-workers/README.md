# Track A compact-record worker count screen

`baseline.rs` is exact selected compact A SHA-256 `4af40353f517f566217b0f882ec25d8002f61d211dcc479c53f8a1dd5de7ed88`. The test binary used a temporary Darwin-only MAP_ANON adjustment and `SD_THREADS` to force worker counts; the selected code remains unchanged. The host reported eight logical CPUs, so twelve workers oversubscribed this ARM host, unlike the official six-P-core/12-thread x86 scoring machine.

After warmup, nine randomized full-seed native shared-ARM runs per count gave median wall 0.13408/0.05675/0.03921/0.04146 seconds for 1/3/6/12 workers. A 15-pair 6/12 repeat gave 0.03897/0.03834 seconds, CPU 0.17141/0.18847 seconds, and median native RSS 260,931,584/272,695,296 bytes. All 72 full-hash executions including warmups passed. Wall ranking was inconsistent; timings are native shared-host screens, not official x86 or cgroup evidence, and no worker count change is recommended. Raw samples are `report.json` and `repeat-6-12.json`.

The exact compact source's existing 132,624-group grid and page-end reference tests covered 6 and 12 workers. Additional `stress-6-12.py` checks passed empty, 40,000 all-escape, 40,000 alternating, and 87,192 out-of-order records across 2,422 endpoints at both counts against the official reference. No Mac Docker was used.
