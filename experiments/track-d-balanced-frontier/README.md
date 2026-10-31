# Track D balanced-frontier comparison

`baseline.rs` is the exact selected meeting-update implementation, SHA-256 `2c4bcd2771cf79eceb37ee309edaeda4675db6f026458f483871f784a268755e`. `meeting.rs` is the isolated balanced-frontier candidate, SHA-256 `1022f4d9c9956b17fd054e96a26d09551eff61936a851edf88505e12e2b1946c`. Both compute all output; no data, credentials, or precomputed answers are included. The candidate selects the smaller heap, breaking ties by smaller minimum distance. It tracks heap length through all pushes, pops, redistributions and clears. The stop rule remains `min_forward + min_backward >= best`.

For nonnegative edges, choosing sides arbitrarily retains correctness if each side pops its own minimum and a successful distance update checks the opposite side. If a shorter path existed when the stop rule fired, a crossing edge between the forward-settled prefix and backward-settled suffix (or an initialized endpoint) would already have recorded a path no longer than it. Stale entries lower the apparent bound and can delay termination; they do not justify an early stop. A Python model separately tests five side-selection policies.

Run on a compatible x86-64-v3 host, with Rust, Python and generated data available:

```
python3 compare.py --data /path/to/full-d --build-dir /tmp/d-balanced-build --report /tmp/d-balanced.json --runs 7
python3 oracle.py /tmp/d-balanced-build/baseline /tmp/d-balanced-build/meeting
python3 exhaustive.py /tmp/d-balanced-build/baseline /tmp/d-balanced-build/meeting
python3 extremes.py /tmp/d-balanced-build/baseline /tmp/d-balanced-build/meeting
python3 proof-model.py
```

`compare.py` compiles both with matching offline release flags and x86-64-v3 on x86, runs randomized paired trials with warmup, verifies every published seed-1 output hash, and records wall/CPU/per-process RSS. Process RSS is not cgroup memory. Use separately generated official full data (generator/reference/spec included); never reuse cached answers. Run single-threaded benchmarks without concurrent load when possible. Linux ru_maxrss is KiB; macOS reports bytes.

On a shared ARM Mac, seven paired native measured full runs all matched seed-1 output; medians were 0.375878 s balanced versus 0.660685 s baseline, CPU 2.030 vs 3.119 s, max process RSS 534,560,768 vs 561,332,224 bytes. One warmup each is in `mac-arm-report.json`. These are not x86/official measurements. Both builds also passed 16,000 randomized directed graph queries against independent Dijkstra, 36,864 all-pairs exhaustive three-node cases against Floyd-Warshall including zero/u32-max weights, a full-size max-weight chain, and 6,000 repeated/unreachable queries. Target x86 and official cgroup measurements, plus independent code review, are necessary before promotion.

An overflow-check-enabled candidate build additionally passed the randomized and exhaustive oracles. Test-only forced 1, 2, 3, 7 and 32-worker builds each passed the 16,000-query randomized oracle. These later checks used the same candidate source and are not included in the earlier Library archive's README.
