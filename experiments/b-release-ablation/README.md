# B mapped-page release ablation (not selected)

`no-release.rs` is selected Rust B with the `madvise(MADV_DONTNEED)` call removed from the per-document scan. It retains all computation and output behavior. Selected baseline SHA-256 is `805b05559c1cf73c14befbaad3f0f7cf0ef94468e64a1192709bbfe7d558ccb1` and candidate source builds with warnings for the now-unused helper.

All sixteen full seed-1 outputs, including one warmup per binary, matched the published output hash. Seven randomized native paired runs on a shared macOS ARM host gave median wall 0.462024 s without release versus 0.437731 s selected, and CPU 2.319166 versus 2.297712 s. Other agents were active; these are noisy local timings, not official scoring-box/cgroup measurements. The selected page-release behavior was retained. See `no-release-bench.json` for raw samples. Linux prewarmed file cache, page accounting, process RSS and cgroup peaks may differ from macOS.
