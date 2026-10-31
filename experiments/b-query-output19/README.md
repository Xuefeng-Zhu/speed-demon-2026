# B query parsing and decimal output (unselected)

The candidate removes the temporary split-word vector for each query, while preserving strict left-to-right Boolean operators, and writes decimal integers through a stack buffer instead of generic string formatting. The exact baseline is selected source SHA-256 `7d371fe84ce9f0fd9d3c7e6fdf02b6b37e0f1440319c654161b990cf27bb8bf3`; candidate SHA-256 is `6d48523bf7dc8ad4fdb57c0b5c8a0a3a7d067551f92c459d1dcc03c47b4d0195`. Phrase summaries, indexing and Boolean evaluation are unchanged. This is an isolated experiment.

One randomized nine-pair warmed full-seed screen on shared macOS ARM gave baseline/candidate median wall 0.232811/0.232150 s and median CPU 1.530774/1.526524 s. All 20 executions including warmups matched the published full-seed result hash. This is an effectively tied preliminary result, not official x86 or cgroup evidence; no alternate-reference, adversarial query, integer-extreme, independent code-review or target testing was performed. No speed-first selection is justified. Raw timing is `arm-report.json`.

Build each source with `rustc --edition=2021 -O -C lto=fat -C codegen-units=1 -C panic=abort`, then run `python3 experiments/b-rust-lengthhash/compare.py --baseline <baseline-binary> --candidate <candidate-binary> --data <independent-full-seed-data> --runs 9 --report <report.json>`. No Docker was run on the Mac.
