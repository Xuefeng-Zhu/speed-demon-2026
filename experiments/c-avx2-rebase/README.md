# Track C AVX2 delimiter search on direct-country baseline — experimental

`baseline.rs` is the exact selected C source SHA-256 `76497615f1abc0bf28a7b0d1d18030ebc263ddf8587d98c263ea5fc9e8840538`. `candidate.rs` is `3f72fb04f7ecde22e60e1bbb1b84e89e6e2bd3dba3bece03a4845db01a5dc68d`. The sole source change is a guarded 32-byte AVX2 delimiter search before the existing SWAR tail. It is compiled only on x86-64 with the build target's AVX2 feature enabled; other targets use the selected parser. Official x86-64-v3 enables it. Country lookup, full-byte name comparisons, aggregation and all other behavior are unchanged; no cached answers or input recognition are used.

On the older `f71a22...` baseline, the parent-run dot VM reported direct AVX2 2.1% and 12.8% faster in two paired native x86 batches; actual x86 property/guard/reference stress passed in a pooled campaign of 333 full hashes. These are native shared VM observations, not official scoring. This rebased `76497615...` pair has **not** been executed or timed on x86 yet; do not attribute the prior measurements to it.

The AVX helper is byte-identical to the previously independently reviewed helper. That review found no bound or first-delimiter defect: the 32-byte load is guarded by remaining slice length, movemask bit order matches byte order, and quote-escape handling remains unchanged. The exact rebased source, on Mac ARM where AVX2 is compiled out, passed the full public hash, 15,145,280 delimiter checks, 76,924 protected-page comparisons, 24 reference corpora × 5 worker counts, and 357 CRLF/quoted-newline cut comparisons. Windows-target x86-64-v3 cross-assembly of the helper contains `vpcmpeqb`/`vpmovmskb`; that is not Linux execution. No Mac Docker was used. Candidate is unselected.

On an x86-64-v3 Linux host, first verify instruction support; generate full seed 1 data separately; execute tests and measurements serialized:

```sh
rustc --edition=2021 -O -C lto=fat -C codegen-units=1 -C panic=abort -C target-cpu=x86-64-v3 experiments/c-avx2-rebase/baseline.rs -o /tmp/c-avx-rebase-base
rustc --edition=2021 -O -C lto=fat -C codegen-units=1 -C panic=abort -C target-cpu=x86-64-v3 experiments/c-avx2-rebase/candidate.rs -o /tmp/c-avx-rebase-candidate
python3 experiments/c-avx2-rebase/check-asm.py --source experiments/c-avx2-rebase/candidate.rs
python3 experiments/c-avx2-rebase/property.py --avx2
python3 experiments/c-avx2-rebase/guard.py --avx2
python3 experiments/c-avx2-rebase/independent.py --avx2 --source experiments/c-avx2-rebase/candidate.rs --seeds 24
python3 experiments/c-avx2-rebase/cut_oracle.py --avx2
python3 experiments/c-nameowned/compare.py --baseline /tmp/c-avx-rebase-base --variant /tmp/c-avx-rebase-candidate --data /path/to/generated-full-c --runs 15 --report /tmp/c-avx-rebase-x86.json
```

Repeat paired timing batches. The comparator checks the public full hash every time and records wall, CPU and process RSS; warmed cgroup peak and official scoring are separate. Property/guard `--avx2` tests assert the actual vector path is compiled, while independent/cut tests use x86-64-v3. Tests without the flag exercise the portable fallback.
