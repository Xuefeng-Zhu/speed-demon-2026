# B no query-phase barrier (not selected)

The isolated candidate removes the worker barrier between indexing and query phases; every worker still owns its own data, so this can overlap stragglers but may increase simultaneous indexing/query memory. On shared ARM Mac 11 randomized warmed full-data pairs all produced the published hash. Median wall was 0.29052 s candidate vs 0.29086 s baseline, CPU 1.6066 vs 1.5997 s. Raw native samples are `report.json`; no stable gain supports promotion. No alternate references, x86 performance or cgroup peak have been established. No Mac Docker was used.
