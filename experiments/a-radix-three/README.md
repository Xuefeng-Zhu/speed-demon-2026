# Three-percentile MSD radix selection (not selected)

This isolated Track A experiment replaces the existing three `select_nth_unstable` calls with four passes of shared multi-rank MSD radix histograms for latency groups of at least 256 records. It computes the same three nearest-rank values without modifying the latency slice; smaller groups keep the selected implementation. It remains unselected and has not received broad randomized/adversarial correctness review.

On shared macOS ARM with 12 workers, seven randomized native full-seed pairs after warmup all matched the published SHA-256. Median wall time was 0.054218 s candidate versus 0.049845 s selected, and median CPU 0.202644 versus 0.196186 s. The candidate was slower, so the screen stopped. `mac-arm-report.json` contains each run; these figures include process startup and native process RSS, not official cgroup memory, and concurrent load was possible. Native binaries changed only the Linux anonymous-mapping constant to Darwin's value. `candidate.rs` is the Linux-source form.

An instrumented full-seed profile found 1,475 groups with at least 256 records totaling 1,436,890 records, but only 4,686 of those records belonged to groups whose observed max–min range was at most 65,535; do not assume a narrow latency range. This profile is input-dependent and not a competition score.

To reproduce, compile the selected Linux source and `candidate.rs` with identical Rust release and CPU settings, then run `python3 experiments/a-rust-percentiles/compare.py --baseline /path/to/base --candidate /path/to/candidate --data /path/to/full-a --report /tmp/radix3.json --runs 7 --threads 12`. Generate the input separately; every run is hash-checked. No Mac Docker commands were used.
