# D best-distance edge pruning (not selected)

This isolated alternative to the D source at 15c6be0 skips relaxation when the new tentative distance is at least the best known full path. All 16 full-data outputs, including warmups, matched the published seed-1 SHA-256, and 80 random directed graphs with 16,000 Dijkstra-oracle queries matched. In seven randomized measured pairs on a shared macOS ARM host, median candidate wall time was 0.784879 s versus 0.670536 s baseline; median CPU was 3.481237 versus 3.244732 s. The extra check made this candidate slower in this screen, so it was not promoted. RSS is native process peak, not cgroup memory. See `mac-arm-bench.json` for all samples.

`main.rs` is the candidate; `compare.py` expects `baseline.rs` and `meeting.rs` alongside itself, so copy the current baseline as `baseline.rs` and this candidate as `meeting.rs` to a temporary comparison directory before use. These are noisy native observations, not x86 or official scores.
