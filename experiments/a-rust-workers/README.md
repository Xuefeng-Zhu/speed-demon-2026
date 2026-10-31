# Rust Track A worker-count experiment

The selected 89795bb source supports the `SD_THREADS` override. On shared macOS ARM, seven randomized-order native full seed-1 runs per count plus warmups matched the published output hash. The baseline source SHA-256 is `9aa7eb44c30fbfc5b701ff9467d26b0a27e765520c5e766ef90d0ea6b04d85fc`; the executable was built from a temporary copy with only the Linux anonymous mmap flag changed for Darwin. Results are in `mac-arm-report.json`.

| Workers | Median wall s | Median CPU s | Median process RSS MiB |
| --- | ---: | ---: | ---: |
| 1 | 0.15191 | 0.14856 | 256.4 |
| 3 | 0.06736 | 0.16923 | 259.6 |
| 6 | 0.05081 | 0.19093 | 265.6 |
| 12 | 0.04951 | 0.20310 | 272.3 |

The six- and twelve-worker timing ranges overlap. Process RSS includes mapped input and is not the official cgroup peak; the official target is x86, so these measurements do not support changing the current choice. For a controlled comparison on a target host, compile the unmodified selected source, then run:

```sh
python3 experiments/a-rust-workers/compare.py --binary /path/to/solution --data /path/to/full-a-data --report /tmp/a-workers.json
```

The driver verifies every output hash and records wall, CPU and `ru_maxrss`. Linux reports `ru_maxrss` in KiB and macOS in bytes. Use a separate warmed cgroup experiment for the competition's memory metric.
