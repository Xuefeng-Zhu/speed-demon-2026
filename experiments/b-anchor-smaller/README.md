# Smaller B phrase-anchor sample (not selected)

The current B uses a 512 KiB input-derived sample to choose a phrase anchor.
The only change in `sample16.rs` and `sample17.rs` is a reduction to 64 KiB and
128 KiB respectively. Each still checks full phrases exactly and computes its
anchor from the current input. Baseline source SHA-256 is
`322cc95ee08cf6d4abc5e1b52240753f66c7eaf89ab669cb6d72b0a8487dc458`;
64 KiB is `81af0e2e5cc0c656d19e2f72fb5d20da530689bca9b6a6c9d49d163125d621a9`,
and 128 KiB is `aa7cb7788a63184192651d0b2f1842e02bb7e58b32ddd707d3bdfefebeeedf79`.

Every full seed-1 output hash matched in warmup plus nine randomized pairs per
variant on the shared ARM Mac. Median wall/CPU seconds were 0.272946/1.678809
for 64 KiB versus 0.257346/1.573459 for its baseline, and 0.281292/1.613934
for 128 KiB versus 0.273571/1.578051 for its baseline. Raw samples are
`sample16-mac-arm.json` and `sample17-mac-arm.json`. These noisy scalar-path
measurements are not target x86 or official cgroup evidence. Neither candidate
was selected; no additional reference suite was run after the slower screen.

Compile both files with identical release flags, then use
`experiments/b-rust-lengthhash/compare.py --baseline /path/to/base --candidate
/path/to/candidate --data /path/to/full --runs 9 --report /tmp/b-sample.json`.
No Docker was used.
