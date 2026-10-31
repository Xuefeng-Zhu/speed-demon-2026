# AVX2 endpoint delimiter scan — experimental

`avx2.rs` replaces the eight-byte endpoint space scan with an AVX2 32-byte scan, then hashes endpoint words using the exact same two-lane operations as `dualhash.rs`. Full endpoint bytes are still checked on hash matches. The scoring CPU has AVX2; the function is compiled only on x86_64, with an ordinary two-lane fallback on other architectures. Each vector load can extend at most 31 bytes past the final line, and `map_file` provides a 4096-byte anonymous pad. Source SHA-256 is printed by `compare.py`.

**The x86 intrinsic path has not been compiled or run yet.** An ARM-native test-only simulation using a bytewise delimiter scan but the same post-scan hash logic matched the published full seed-1 hash, all 1,803 adversarial legal endpoint patterns across six worker counts and the page-end reference suite. This does not test x86 intrinsics, page faults, x86 performance or official scoring. Do not promote until those checks and an independent review pass. Native x86 build uses `-C target-cpu=x86-64-v3` by default and explicitly enables AVX2 on the scanner function.

The commands below refer to the Library transfer archive, which contains its comparator and test scripts. Run from the unpacked archive with full seed-1 data generated separately:

```
python3 compare.py --data /path/to/full-a --threads 12 --runs 9 --report /tmp/a-avx.json
rustc --edition 2021 -O -C lto=fat -C codegen-units=1 -C panic=abort -C target-cpu=x86-64-v3 avx2.rs -o /tmp/a-avx
python3 tests/test.py --binary /tmp/a-avx --io directories
python3 tests/page_end_test.py --binary /tmp/a-avx --reference official/reference/a_ingest.py
python3 tests/latency_grid_test.py --binary /tmp/a-avx
python3 tests/stress-portable.py --binary /tmp/a-avx --reference official/reference/a_ingest.py
python3 tests/stress-growth.py --binary /tmp/a-avx --reference official/reference/a_ingest.py
```

Also test a forced-collision version by replacing `let (e, h) = unsafe { endpoint(d, s) };` with `let (e, _h) = unsafe { endpoint(d, s) }; let h = 0;` in a test-only copy and run the stress scripts. The comparator randomizes order, checks every output hash, records CPU/wall/process RSS and invokes no network. Process RSS is not official cgroup memory. No datasets, credentials, or binaries are included.
