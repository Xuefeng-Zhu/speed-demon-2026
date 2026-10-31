# Track A count and hash screens

These isolated, unselected variants are based on the selected Track A source SHA-256 `9aa7eb44c30fbfc5b701ff9467d26b0a27e765520c5e766ef90d0ea6b04d85fc`. `rotate.rs` replaces the endpoint hash's per-word multiply with rotate/XOR and a final multiply. Exact byte comparisons remain, but the linear mixer may have structured collision families and has not been adversarially assessed. `counts.rs` accumulates per-hour, per-local-endpoint counts and errors during parsing, removing the summary's first pass over records. Neither has received full edge-case review; neither is selected.

Each screen used 11 randomized full seed-1 pairs after warmups, 12 workers and Rust 1.95.0 on a shared Mac ARM host. Temporary copies changed Linux's anonymous-mmap flag `0x20` to Darwin's `0x1000`; the files here retain the Linux flag. Every output matched published SHA-256 `495ca09682b9673ef836a506496177680bb4a3af54255174befddb1f83481cd3`.

| Variant | Median wall, candidate vs baseline | Median CPU, candidate vs baseline |
| --- | --- | --- |
| rotate | 0.04134 vs 0.04193 s | 0.19152 vs 0.19264 s |
| counts | 0.04432 vs 0.04351 s | 0.19934 vs 0.20109 s |

`report.json` and `counts.json` retain all measured samples and hash the Darwin-adapted sources. These differences are small and may reflect contention; they do not demonstrate an x86 or official scoring-machine speedup. Native RSS is not official cgroup memory. No Docker was used.

`cache16.rs` modifies the existing experimental `a-timestamp-cache/cache.rs` endpoint hint to mix the first 16 input bytes instead of eight. A hit still checks the endpoint's exact bytes and following delimiter; short endpoints may hash differently depending on subsequent status/latency text, affecting cache performance only. In 11 randomized pairs it ran in 0.04255 s versus baseline 0.04332 s, but in a 15-pair repeat it ran in 0.06207 s versus 0.05207 s; corresponding CPU medians in the repeat were 0.21378 and 0.20202 s. Every full hash passed. The inconsistent timing does not justify promotion; it has not received alternate-input review. The raw samples are `cache.json` and `cache-repeat.json`.
