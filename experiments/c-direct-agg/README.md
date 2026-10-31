# C direct record aggregation (not selected)

`baseline.rs` is the selected CRLF candidate. `candidate.rs` replaces the hot-loop construction and generic `merge` call with direct count, sum, min/max and length field updates; the final cross-worker merge is unchanged. This experiment was screened only and is not selected.

After one warmup, all 22 measured full seed-1 outputs matched the published hash. Eleven randomized native ARM pairs on a very heavily contended Mac produced candidate/baseline median wall 0.39015/0.39005 s and CPU 1.16240/1.08790 s. Results are in `arm-report.json`; the timing does not support a speed win, and is not x86, cgroup or official scoring. No alternate-input correctness or independent review was attempted. No Docker was run on the Mac.
