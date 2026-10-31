# Track A endpoint-prefix cache (not selected)

This isolated experiment adds a per-table cached masked first 8 bytes for exact endpoint comparison. It retains the hash, length check and full byte comparison of the remainder; it avoids re-reading those bytes from the prior mapped record. `baseline.rs` is the selected Linux source and `candidate.rs` is the Linux candidate; no selected code was changed.

On the shared macOS ARM host, temporary builds changed only the anonymous-mmap flag (Linux 0x20 to Darwin 0x1000). Seven randomized measured full seed-1 pairs at 12 workers gave candidate 0.05668 s versus baseline 0.05788 s, while a 15-pair repeat reversed the ordering: 0.05826 versus 0.05675 s. CPU medians in the repeat were 0.21262 versus 0.21281 s. Every full hash matched. The small inconsistent result does not justify promotion and cannot establish x86 performance. This prototype has not received alternate-input or collision review.

`screen.json` and `repeat.json` record the Mac runs, including source hashes of the Darwin-adapted temporary files. No Docker was used. To reproduce, copy the Linux files into an isolated directory as `baseline.rs` and `dualhash.rs`, copy `experiments/a-dualhash/compare.py` alongside, adapt the mapping flag only if on macOS, then run that comparator with separately generated full seed-1 data.
