# A 4/5-digit latency fast path (not selected)

Against the selected `track-a/src/main.rs` at `e88ee2c`, this isolated candidate special-cases four- and five-digit latencies using two decimal pairs before falling back to the original parser. It is input-derived and handles all other legal latencies via the original code. The Mac test build changed only the anonymous-mapping flag from Linux 0x20 to Darwin 0x1000.

Ten randomized paired full-seed runs after one warmup all matched the published output hash. On the shared Mac ARM host, median wall time was 0.05715 s candidate versus 0.05255 s baseline, median CPU 0.20879 versus 0.19780 s. Ranges overlapped (0.04879–0.06676 s candidate, 0.04876–0.06023 s baseline). Raw results are in `mac-arm-report.json`; no alternate-input correctness suite was run because the screen was slower. These are nonofficial measurements and no source change was selected. No Docker was used.
