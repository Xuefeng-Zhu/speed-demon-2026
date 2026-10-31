# Track C fused field and numeric scan (experimental)

This is a portable, source-only comparison. `baseline.rs` is byte-identical to the selected CRLF implementation at 073646e, SHA-256 `3e181c76981348a96b48470844ee0f8988847d32164ff935a211024861c86ad4`. `candidate.rs` SHA-256 `a8fd13429d718e1b58195953ac295e5b8ff5ecce6edc469dee0908c9836f24d1` combines libc `memchr` for field delimiters with the fixed-two-fraction numeric scanner. It preserves exact name equality and all aggregation logic. As with the baseline, CRLF synchronization and the number scanner rely on the officially permitted §2.2 guarantees for every seed including holdout; this is not an implementation of unrestricted §2.1 input. Neither source contains cached answers or data recognition.

The candidate matched the published full output on every local run, 120 mixed reference comparisons and 357 CRLF/bare-LF/quoted-newline/boundary reference comparisons. Its numeric function is byte-identical to `numeric-property.rs`, which checked every permitted cent value and integer delimiter under overflow checks. Two shared ARM Mac screens gave median candidate vs baseline 0.2928 vs 0.3274 s (7 pairs), and 0.2526 vs 0.3750 s (15 pairs). These wall times varied widely under contention; CPU medians were 0.9527 vs 1.0117 s and 0.8762 vs 1.0693 s. This is not x86 or official evidence. See `report.json` and `repeat.json`.

On x86-64-v3 with Rust and Python installed, generate the full input independently and execute correctness before timing:

```sh
rustc --edition=2021 -O -C lto=fat -C codegen-units=1 -C panic=abort -C target-cpu=x86-64-v3 baseline.rs -o /tmp/c-fused-base
rustc --edition=2021 -O -C lto=fat -C codegen-units=1 -C panic=abort -C target-cpu=x86-64-v3 candidate.rs -o /tmp/c-fused-candidate
python3 experiments/c-rust-independent.py --source candidate.rs --seeds 24
python3 experiments/c-crlf-boundary/cut_oracle.py
rustc --edition=2021 -O -C overflow-checks=yes numeric-property.rs -o /tmp/c-fused-numeric && /tmp/c-fused-numeric
python3 independent-verify.py --baseline baseline.rs --candidate candidate.rs
python3 compare.py --baseline /tmp/c-fused-base --variant /tmp/c-fused-candidate --data /path/to/generated-full-c --runs 15 --report /tmp/c-fused-x86.json
```

The comparator warms both versions, randomizes pair order, checks every published full-output SHA-256 and records wall, CPU and per-process RSS. On Linux RSS is KiB, not warmed cgroup memory. Run serialized without competing benchmarks; check target cgroup and official score separately. The `experiments/c-crlf-boundary/candidate.rs` copy is byte-identical to the root candidate and is used by the portable cut fixture. The numeric property contains the identical `number` function; confirm source identity if changing either copy. No datasets, credentials, binaries or Git metadata are included.

An independent review found no defect under §2.2/§2.3; `independent-verify.py` extracts the actual baseline and candidate field and number functions before compiling the property harness, which checked 20,200,029 numeric and 19,547 field cases with overflow checks.
