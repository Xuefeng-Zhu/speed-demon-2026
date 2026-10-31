# Track C guarded SWAR parser experiment

`baseline.rs` is the exact selected CRLF source (SHA-256 `3e181c76981348a96b48470844ee0f8988847d32164ff935a211024861c86ad4`); `candidate.rs` is `f71a22c0642250010d967cfb493fbfb95bab01f1c3e4dedac0b93fb2987e80ef`. The only changes are guarded 8-byte delimiter scanning and guarded decimal id/region-id decoding with original scalar fallback. The original locked dictionary and aggregation remain unchanged. Both variants derive all output from input. They rely on the official §2.2 CRLF and name guarantees for generated holdouts, not unrestricted CSV §2.1 alone. No external dependencies, data or cached answers are included.

Two 15-pair full-seed ARM Mac screens after warmup measured candidate/baseline median wall 0.11433/0.14025 s and 0.11077/0.12986 s; CPU 0.68324/0.82709 and 0.69170/0.83765 s respectively. All 64 executions matched the published full hash. Shared host load can vary, and these are not x86, cgroup or official results; `arm-report.json` and `arm-repeat.json` preserve raw samples. Candidate has not been selected.

Exact-source local validation passed 120 mixed reference comparisons, 357 hostile CRLF/quoted-newline cut comparisons, 15,145,280 delimiter checks, 76,924 macOS guard-page cases, 10,001,599 integer cases, 36 integer guard-page cases, 19,547 field cases and 20,200,029 comparisons of unchanged amount parsing. The initial copied field verifier accidentally included the new helper in a scalar-number extraction and failed to compile; it was corrected to extract only the exact function and then passed. Linux guard, compiler, x86 timing and official sandbox remain to be checked. No Mac Docker was used.

In this transfer archive, from its root, generate full seed 1 input separately with `official/generators/c_join.py` and run serialized without competing benchmarks:

```sh
rustc --edition=2021 -O -C lto=fat -C codegen-units=1 -C panic=abort -C target-cpu=x86-64-v3 experiments/c-parser-swar/baseline.rs -o /tmp/c-parser-base
rustc --edition=2021 -O -C lto=fat -C codegen-units=1 -C panic=abort -C target-cpu=x86-64-v3 experiments/c-parser-swar/candidate.rs -o /tmp/c-parser-candidate
python3 experiments/c-parser-swar/independent-adversarial.py
python3 experiments/c-parser-swar/field-property.py
python3 experiments/c-parser-swar/field-guard.py
python3 experiments/c-parser-swar/integer-property.py
python3 experiments/c-parser-swar/integer-guard.py
python3 experiments/c-parser-swar/independent-verify.py --baseline experiments/c-parser-swar/baseline.rs --candidate experiments/c-parser-swar/candidate.rs
python3 experiments/c-rust-independent.py --source experiments/c-parser-swar/candidate.rs --seeds 24
python3 experiments/c-parser-swar/cut_oracle.py
python3 experiments/c-nameowned/compare.py --baseline /tmp/c-parser-base --variant /tmp/c-parser-candidate --data /path/to/generated-full-c --runs 15 --report /tmp/c-parser-x86.json
```

The comparator randomizes paired order after warmup and validates the official output hash every run; RSS is process RSS, not a warmed cgroup peak. Repeat paired batches, retain raw samples, and validate on the official board if target evidence and independent review support selection.

An independent reviewer extracted the actual candidate into a test harness and checked all 1–9,999,999 positive values, sampled longer fallback values and offsets, 652,800 delimiter byte/alignment cases, 200,000 randomized buffers and encoded field round trips with overflow checks. `independent-adversarial.py` and its tail preserve those tests. This is not Linux performance evidence.

A second independent reviewer found no defect under §2.2 and reran both protected-page/property suites and 24 mixed corpora at five worker counts against the reference. All passed. Independent review does not establish Linux timing or machine compatibility.

## Dot VM x86 comparison

The parent-run native x86 paired batches reported 7.4–21.0% lower wall time with lower CPU and unchanged native RSS versus the exact baseline. Across C parser, B grouped lookup and D mmap packages, 164 full hashes, 24 alternate comparisons, Linux/AVX2 guard-page, collision, boundary and graph-oracle checks passed. These are shared VM results rather than official scoring-box or parent-cgroup metrics. This candidate is selected for official practice.
