# C 12-byte events with exact owner-row cache (unselected)

This isolated rebase changes the 16-byte `Event` payload to a 12-byte `repr(C)` `(offset:u32, len:u16, group:u16, fingerprint:u32)`. The parser still computes the existing full 64-bit hash and uses it to choose the owner. The owner receives only the low 32 bits. Its row cache verifies the fingerprint and exact name bytes, and its existing eight-entry collision chain promotes to an independently salted exact-name map. Equal names have the same deterministic full hash and therefore the same owner and fingerprint; unrelated names that share low32 remain separate through full-byte comparison. The fallback for non-packable mappings is unchanged. This is based on the earlier `c-owner-salted32` idea, now rebased to the selected fused parser and owner-row cache. The selected source is unchanged; this is a candidate, not a performance claim.

Baseline SHA-256 `76b341e2b7e880fe4ceeee220206a63b48cd247bba4448aa7991a7ad825e8dd2`; candidate SHA-256 `5447d5c7d77e616b60c843c20f58cacc6bd152e6c9337e1a417f7b1768d863aa`. Lower-entropy fingerprints cause extra equality comparisons and map promotions in deliberately colliding inputs; seeded fallback limits chain length, but full-hash owner concentration still has no fixed worst-case work guarantee. True >4 GiB input parsing and official cgroup memory are not established.

Run `python3 experiments/c-rowcache-salted32/verify.py` from the repository root; use `--avx2` only on an x86-64-v3 CPU. This independently checks random reference corpora, forced full-hash collisions, replacement and promotion, a `repr(C)` size assertion, plus same-low32 real distinct 64-bit hashes that either share or differ in their owner. Benchmark full public data separately with the exact baseline and candidate under matching release flags; all outputs must be verified. Target SIMD, performance, cgroup and holdout remain untested unless explicitly recorded below.

Local native ARM `verify.py` passed 24 corpora × five worker counts against the official reference, eight forced-constant-hash corpora × five worker counts, direct cache replacement and promotion models, independent cache stress at one and 32,768 slots, and an overflow-checked low32 suite. The latter asserts `Event` is 12 bytes, promotes 50,000 synthetic names sharing one fingerprint, and discovers real syntactically legal distinct names with equal low32 hashes both within one owner and across two owners. These are not x86 SIMD, full-seed performance, hidden-data or cgroup results.

## Native ARM screening

Two serialized randomized 15-pair warmed full public seed-1 batches passed all 64 output hashes. Median baseline/candidate wall was 0.083915/0.079986 s and 0.086937/0.084512 s; CPU 0.405965/0.385943 s and 0.447684/0.434549 s. Median process RSS was 285,917,184/272,564,224 bytes and 286,769,152/273,072,128 bytes. The shared host may vary; this is neither x86 nor official scoring and does not measure parent cgroup peak. Raw observations are in `arm-report.json` and `arm-repeat.json`.

For a serialized x86 test, extract this archive at its root on a machine with an AVX2-capable x86-64-v3 CPU, independently generate the full seed-1 data, then:

```sh
python3 experiments/c-rowcache-salted32/verify.py --avx2
rustc --edition=2021 -O -C lto=fat -C codegen-units=1 -C panic=abort -C target-cpu=x86-64-v3 experiments/c-rowcache-salted32/baseline.rs -o /tmp/c-low32-baseline
rustc --edition=2021 -O -C lto=fat -C codegen-units=1 -C panic=abort -C target-cpu=x86-64-v3 experiments/c-rowcache-salted32/candidate.rs -o /tmp/c-low32-candidate
python3 experiments/c-rowcache-salted32/compare.py --baseline /tmp/c-low32-baseline --variant /tmp/c-low32-candidate --data /path/to/full-c --runs 15 --report /tmp/c-low32-x86.json
```

Repeat paired timings and check actual SIMD and official cgroup memory separately. No dataset, credential or cached answer is included in the archive.

Independent static review found no new defect in owner routing, low32 collision handling, stable row caches, exact-name comparisons, 12-byte alignment, mapping/sentinel fallbacks or owner-local concurrency. Full hash routing precedes truncation; distinct low32 collisions cannot merge without byte equality. This is not an exhaustive concurrency proof, actual full >4 GiB parsing, x86 execution or cgroup measurement.

The additional independent model in `experiments/c-salted32-independent/` passed 1,920,000 operations over 1, 3 and 12 owners, including real and synthetic low32 collisions, same-slot cache replacement, promotion, 257 groups, escaped, trailing-space and empty names, and 65,535/65,536-byte sentinels. Run `python3 experiments/c-salted32-independent/run.py`; its synthetic hashes test routing and exact equality rather than `name_hash`. It does not establish real >4 GiB parsing, x86 SIMD behavior or a total cgroup bound.
