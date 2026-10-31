# Rust C dictionary experiments

These are isolated alternatives to the selected checked Rust C at commit `1b2da3d`, source SHA-256 `ac9ed25ac4685cc67e66b0db1d0208ae3e87c5e88f408cf7ed3db0fdb4968e72`. Both preserve exact-byte name comparisons and use the existing live mmap as backing storage. They are not selected or independently validated for all legal CSV inputs.

- `borrow.rs` replaces owned boxed names in each shard map with borrowed name slices. Six randomized-order measured full seed-1 pairs after warmup on a shared ARM macOS host had median wall 0.2046 s borrowed versus 0.1854 s selected and median CPU 1.098 versus 0.986 s. Maximum process RSS was 224,067,584 versus 225,853,440 bytes.
- `prehashed.rs` additionally stores the previously calculated hash in the dictionary key to avoid hashing each name again, still resolving collisions by exact name bytes. Six equivalent pairs had median wall 0.2563 s versus 0.2517 s selected, median CPU 1.136 versus 1.014 s, and maximum process RSS 227,524,608 versus 225,869,824 bytes.

All 28 executions, including four warmups, matched the published full output SHA-256. The results are in `borrow-report.json` and `prehashed-report.json`. Host contention was present; process RSS includes file-backed pages and does not represent the warmed-cgroup metric. The ARM native measurements are not official x86 scores, and neither idea justifies promotion on this evidence.

`compare.py --baseline /path/to/selected --variant /path/to/variant --data /path/to/full-c --report /tmp/c-dict.json` compiles nothing and compares already-built binaries, checks every hash and records process wall/CPU/RSS. Use equivalent compiler flags and separate cgroup measurements for a serious target comparison.
