# Independent review of no-prefault candidate

The selected `track-a/src/main.rs` hashes to `9aa7eb44c30fbfc5b701ff9467d26b0a27e765520c5e766ef90d0ea6b04d85fc`; `experiments/a-ablation/no-madvise-linux.rs` hashes to `16ae5a2e4df27269dbcc2f7b21bb9ad1022081d84e68e5b2c3f5b122a7cb04e2`. Their only difference replaces the `MADV_POPULATE_READ` call, whose return value is ignored, with a no-op using the existing locals. It removes the optional prefault hint; mapping, byte parsing, grouping, output, and error handling are unchanged. On stable, readable input the kernel supplies mapped pages lazily. I/O behavior, page faults, time, and memory can differ, so Linux target benchmarking remains required.

The candidate was built with Rust 1.95.0, `--edition 2021 -O -C lto=fat -C codegen-units=1 -C panic=abort`, from a temporary source copy changing only the Linux anonymous mapping flag `0x20` to Darwin `0x1000`. It emitted the expected harmless unused-`madvise` warning. On the Mac ARM process, the following passed:

- Full seed-1 output SHA-256 `495ca09682b9673ef836a506496177680bb4a3af54255174befddb1f83481cd3`, 12 workers.
- Existing holdout output byte-compared to the reference, SHA-256 `04168fcd480940157d8221e2ce79e49a3e8f41d4c66cbc3634edd1cb5c91c242`, 12 workers.
- `track-a-verification/test.py --binary /tmp/a-nomadvise-review --io directories`: independent synthetic oracle, empty, 1,000, and two 100,000-record cases.
- `track-a-verification/page_end_test.py --binary /tmp/a-nomadvise-review --reference official/reference/a_ingest.py`: 14 file sizes around page boundaries at workers 1, 2, 3, 6, 12, and 64, byte-compared to the reference.
- `track-a-verification/latency_grid_test.py --binary /tmp/a-nomadvise-review`: 132,624 singleton groups spanning all 72 hours, latency decimal widths and extreme values, workers 1, 2, 6, 12, and 64.
- `experiments/a-dualhash/stress-portable.py --binary /tmp/a-nomadvise-review --reference official/reference/a_ingest.py`: 1,803 endpoint patterns, lengths 1–125, worker counts 1, 2, 3, 7, 12 and 32, reference SHA-256 `dd9fecaf57f04ea2aee754a4e02a22aaf0a081ef035513346aa40beb2f229919`.

These are correctness checks of the Darwin-adapted executable, not Linux syscall, official sandbox, or scoring-machine performance validation. No Docker was used.
