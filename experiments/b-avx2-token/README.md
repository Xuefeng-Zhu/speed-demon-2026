# Experimental B AVX2 tokenizer: x86 evaluation required

`baseline.rs` is the exact selected Track B source at commit 4f2d688 (SHA-256 `805b05559c1cf73c14befbaad3f0f7cf0ef94468e64a1192709bbfe7d558ccb1`). `candidate.rs` replaces only the document tokenizer with a guarded 32-byte AVX2 alphanumeric classifier on x86-64, a scalar fallback on non-AVX2 machines, and a libc `memchr` line-end search. Its bounded phrase summaries, bitmap cap, dictionary and query logic are unchanged. AVX2 loads occur only when at least 32 bytes remain before the current line end. This is experimental and not selected.

The later selected eight-byte transition scanner at commit 147d5b4 is faster than this package's baseline on official practice. Compare the AVX2 candidate directly against that newer selected source as well before deciding; a win only over the older baseline is insufficient.

**The actual AVX2 path has not been executed.** The intrinsic body typechecked as an x86_64 Windows object only; that is not a Linux runtime test. The ARM scalar fallback passed 40 randomized references, shard/overlap and >1 MiB boundaries, a 4,120-document adversarial alignment/UTF-8 reference fixture, the independent 3,072-document alignment fixture, and all 8 outputs in a three-pair full-data comparison. In that native ARM screen the fallback median was 1.401 s vs 1.029 s for baseline, with CPU 2.810 vs 2.553 s; shared host contention and scalar fallback make these irrelevant to x86 AVX2 speed. No Mac Docker was used.

Additional scalar-fallback builds forced to 1, 2, 3, 7, 12 and 32 workers each matched the 4,120-document independent reference fixture. These checks do not exercise the x86 intrinsic.

On an AVX2-capable Linux x86-64 VM, from this archive's directory, compile with the exact same flags and **run correctness checks before benchmarking**:

```sh
rustc --edition=2021 -C opt-level=3 -C lto=fat -C codegen-units=1 -C panic=abort -C target-cpu=x86-64-v3 baseline.rs -o /tmp/b-avx-base
rustc --edition=2021 -C opt-level=3 -C lto=fat -C codegen-units=1 -C panic=abort -C target-cpu=x86-64-v3 candidate.rs -o /tmp/b-avx-candidate
python3 verify-classifier.py
rustc --edition=2021 -C opt-level=3 -C overflow-checks=yes -C target-cpu=x86-64-v3 classifier-property.rs -o /tmp/b-avx-classifier
/tmp/b-avx-classifier
python3 independent-review.py /tmp/b-avx-base /tmp/b-avx-candidate
python3 alignment.py /tmp/b-avx-candidate official/reference/b_index.py
export B_RUST_BINARY=/tmp/b-avx-candidate
python3 tests/b-bounded-fuzz.py "$PWD/tests/b-rust-positional-adapter.py"
python3 tests/b-bounded-shards.py "$PWD/tests/b-rust-positional-adapter.py"
python3 tests/b-bounded-boundary.py "$PWD/tests/b-rust-positional-adapter.py"
python3 tests/b-bounded-duplicates.py "$PWD/tests/b-rust-positional-adapter.py"
python3 forced-workers.py
python3 compare.py --baseline /tmp/b-avx-base --candidate /tmp/b-avx-candidate --data /path/to/separately-generated-full-b --runs 9 --report /tmp/b-avx-report.json
```

The classifier property verifies every byte at every lane with four fills, 200,000 random vectors, and vector loads adjacent to inaccessible guard pages. `verify-classifier.py` confirms its classifier body matches `candidate.rs`. Independent reference fixtures include UTF-8 high bytes, upper case, all token lengths 1–32, long/empty lines and every 32-byte alignment. `forced-workers.py` compiles temporary 1/2/3/7/12/32-worker versions and checks references. Full input is not included; generate it independently from the included official generator. Benchmark serialization, cgroup memory and the official score need separate measurement. No file contains cached answers or input-recognition shortcuts.
