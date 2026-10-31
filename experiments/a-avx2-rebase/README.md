# Track A AVX2 endpoint-scan comparison (experimental)

`baseline.rs` is the exact selected no-prefault A at commit 82b8d81 (SHA-256 `16ae5a2e4df27269dbcc2f7b21bb9ad1022081d84e68e5b2c3f5b122a7cb04e2`). `dualhash.rs` is the previous two-lane SWAR scanner with prefault removed; `candidate.rs` is the existing 32-byte AVX2 scan with the same two-lane hash and prefault removed (SHA-256 `ffa657cb83f209bdcaf8898a12b7bb917dd6c0f4b4dac509f26b3d37d67a9aeb`). The only behavioral change relative to the original AVX experiment is omission of optional MADV_POPULATE_READ. Candidate AVX scans for the endpoint space in 32-byte loads and then hashes the endpoint in two independent lanes. Full byte equality is retained. The non-x86 build uses the corresponding scalar two-lane path.

**The actual x86 AVX2 path has never been run or timed**. On shared macOS ARM a temporary Darwin anonymous mmap flag adjustment executed only the scalar fallback: four full-hash measured runs plus warmups per side passed, as did independent 0/1,000/100,000/100,000-record oracle tests, 14 page-end tests, and 132,624 group latency grid tests at workers 1/2/6/12/64. This is neither x86 validation nor official evidence. The original AVX source was tested on ARM fallback with 1,803 legal endpoint patterns; the no-prefault rebase is semantically equivalent for outputs. The scanner may read 31 bytes after a delimiter; the mapped file is followed by a 4 KiB zero-filled pad. This assumption needs independent review and target tests.

From the archive root on a disposable Linux x86-64-v3 VM (Rust installed, independently generated full seed-1 dataset), with no competing benchmark:

```sh
for n in baseline dualhash candidate; do rustc --edition=2021 -O -C lto=fat -C codegen-units=1 -C panic=abort -C target-cpu=x86-64-v3 "src/$n.rs" -o "/tmp/a-avx-$n"; done
python3 tests/test_avx2.py --source src/candidate.rs
python3 tests/test.py --binary /tmp/a-avx-candidate --io directories
python3 tests/page_end_test.py --binary /tmp/a-avx-candidate --reference official/reference/a_ingest.py
python3 tests/latency_grid_test.py --binary /tmp/a-avx-candidate
python3 tests/stress-portable.py --binary /tmp/a-avx-candidate --reference official/reference/a_ingest.py
python3 tests/stress-growth.py --binary /tmp/a-avx-candidate --reference official/reference/a_ingest.py
python3 tests/make-forced.py --source src/candidate.rs --output /tmp/a-avx-forced.rs
rustc --crate-name a_avx_forced --edition=2021 -O -C lto=fat -C codegen-units=1 -C panic=abort -C target-cpu=x86-64-v3 /tmp/a-avx-forced.rs -o /tmp/a-avx-forced
python3 tests/stress-portable.py --binary /tmp/a-avx-forced --reference official/reference/a_ingest.py
python3 tests/stress-growth.py --binary /tmp/a-avx-forced --reference official/reference/a_ingest.py
python3 tests/compare.py --baseline /tmp/a-avx-baseline --candidate /tmp/a-avx-candidate --data /path/to/full-a --report /tmp/a-avx-vs-selected.json --threads 12 --runs 15
python3 tests/compare.py --baseline /tmp/a-avx-dualhash --candidate /tmp/a-avx-candidate --data /path/to/full-a --report /tmp/a-avx-vs-dual.json --threads 12 --runs 15
```

`test_avx2.py` compiles the **actual** AVX2 endpoint function and the source's scalar fallback together from the exact supplied source, and compares results for lengths 1–125, 32 alignments, and two page/guard layouts (8,000 cases). It has not yet been executed on x86. Guard tests cover readable bytes up to the pad's limit, not every full-program mapping condition. Test forced table collisions on x86 by generating a temporary copy with the two `endpoint` call results' hashes replaced by `0`, then run the independent reference/growth scripts; never modify the candidate in place. Run page, alignment and collision tests against actual x86 binary. Comparator randomizes order, warms binaries, checks every published full seed-1 hash and reports native process RSS and CPU; these are not official warmed cgroup scores. `official/LICENSE` covers the included official files. No datasets, credentials or binaries are included. Do not promote without x86 and official measurements, broad correctness checks and review.
