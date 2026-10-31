# Separate short query-term interning (experimental, not selected)

Based on exact dynamic-query baseline `7d371fe84ce9f0fd9d3c7e6fdf02b6b37e0f1440319c654161b990cf27bb8bf3`. During query planning, intern <=8-byte terms in a temporary table keyed by the short hash; long terms use the existing table. The short table is then rebuilt at its original compact size for corpus scanning. The candidate is isolated and not selected.

On shared native ARM, randomized batches of 9 and 15 full-seed pairs plus warmups produced wall medians 0.28616/0.35039 s and 0.44005/0.41638 s candidate/baseline; CPU medians were 1.52969/1.52980 and 1.55334/1.55800 s. All 52 output hashes passed. `report.json` and `repeat.json` preserve raw data. Wall varied with load, and unchanged CPU does not support a repeatable gain. No alternate references, forced collisions, independent review, x86 or cgroup tests were performed. Do not select.
