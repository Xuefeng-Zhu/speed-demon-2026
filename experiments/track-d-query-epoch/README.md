# Track D epoch comparison

Compare exact meeting-update baseline (SHA-256 `2c4bcd2771cf79eceb37ee309edaeda4675db6f026458f483871f784a268755e`) with experimental epoch candidate (SHA-256 `d35e13501fbe584a80ad5d16f8a3fd8f1c629d9e9affbe7622ffcfb34a2b6900`). The candidate uses a packed 53-bit distance and 11-bit per-query epoch to avoid per-query touched-vertex clearing, resets the array after 2047 epochs, and retains full u64 sums. It is experimental, not selected.

The exact full specification has at most 1,740,512 nodes and uint32 edge weights; any settled simple path plus one edge is at most 7,475,442,116,555,040, below the 53-bit maximum 9,007,199,254,740,991. The candidate asserts on overflowing that representation; independent review of that bound and wrap behavior is required before promotion.

On shared macOS ARM, seven randomized paired measured runs after one warmup all matched the published full seed-1 hash. Median wall 0.535393 s candidate vs 0.594109 s baseline; CPU 2.698336 vs 2.914666 s; maximum native process RSS 535,166,976 vs 559,251,456 bytes. This is not a scoring-box, x86, cgroup, or cold-cache score. Both passed 80 directed random graphs/16,000 independent Dijkstra queries; forced-single-worker candidate passed the full-size max-weight chain and 6,000 alternating queries crossing epoch wrap multiple times.

On the x86 VM generate the official full seed-1 data separately, install no dependencies, and run:

    python3 compare.py --data /path/to/full-d --build-dir /tmp/d-epoch-build --report /tmp/d-epoch-x86.json --runs 7
    python3 oracle.py /tmp/d-epoch-build/baseline /tmp/d-epoch-build/meeting
    python3 make_single.py && rustc --edition=2021 -C opt-level=3 -C lto=fat -C codegen-units=1 -C panic=abort /tmp/d-epoch-single.rs -o /tmp/d-epoch-single
    python3 extremes.py /tmp/d-epoch-single

The paired benchmark defaults to x86-64-v3 on x86, verifies every full hash and records wait4 wall/CPU/RSS. Linux process RSS is KiB and is not cgroup memory. Use fresh output folders, warm input and compare official-cgroup peaks separately when possible. Do not use input recognition, generated answers, or the saved timing report as code. No dataset or credential is included.

Independent review found no defect under the full-scale bound. A forced-one-worker build also passed 16,000 varied queries against Floyd–Warshall through multiple wraps; output SHA-256 `476b967ba26fc4df8f56090dcd200bb4e255e9bc4e15f7727b26fd9632ca7d12`. Run `python3 wrap-review.py /tmp/d-epoch-single` after building the forced-one-worker candidate.
