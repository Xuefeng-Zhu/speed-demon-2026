# Fused Track C name scan and hash experiment

Unselected isolated experiment against Track C source SHA-256 `0aa4cbccf08b05a59aadbe7eaf23a931e468a95f76463a95100a142e8221bc08`. Candidate `candidate.rs` SHA-256 `6e12627e96f0a0433e567413ccacc1a5d7fdf2de8f4781a3f826c260499783dd`.

The compact path scans ordinary quoted names in 8-byte chunks and feeds a deterministic streaming prehash while looking for the closing quote. Escaped quotes and other cases use the existing parser followed by the same streaming hash. Quoted and unquoted empty names hash equally. Owners still compare exact encoded name bytes and promote hash collision chains; the separate over-4-GiB/group-limit fallback keeps its original hash and dictionary. This deliberately changes owner routing, and a crafted collection of equal hashes or clustered routing can still overload one owner, as with the selected deterministic prehash. Correctness relies on the §2.2 holdout encoding guarantees. An independent static review found no correctness defect under those guarantees; x86 AVX2 execution remains untested.

Validation on macOS ARM with exact candidate:

- `property.py`: alignment and name lengths 0–256, escape pairs at all positions, long names 65,534–131,071 bytes, and both empty encodings; overflow checks enabled.
- `guard.py`: actual `mmap` plus `mprotect(PROT_NONE)`, fields ending at page boundary and explicit quote pairs at 7/8, 31/32 and final boundaries.
- `reference.py --source experiments/c-fused-namehash/candidate.rs --seeds 24`: 24 hostile corpora × 5 worker counts.
- `edge.py`, `groups.py`, `collision.py`, `gate.py`, `owner-property.py`, `cut_oracle.py`: 20 long-name/sentinel, routing-collision and fallback cases; 20 lookup edge cases; 12 collision/growth cases; representability boundaries; 1,007,168 owner-range checks; 357 record-cut/reference comparisons.
- Full seed-1 output SHA checked on every native benchmark execution (48 outputs).

Paired native ARM timing on shared Mac, `rustc -O -C lto=fat -C codegen-units=1 -C panic=abort`, compared with exact selected baseline. Nine pairs: median wall 0.07510 vs 0.08111 s (7.4% faster), median CPU 0.4494 vs 0.4898 s (8.3% lower), median RSS 270.63 vs 271.44 MiB. Fifteen-pair repeat: wall 0.08304 vs 0.08554 s (2.9% faster), CPU 0.4619 vs 0.4942 s (6.5% lower), RSS 270.36 vs 270.97 MiB. Raw results: `arm-report.json`, `arm-repeat.json`. Mac process RSS is not official cgroup peak, and ARM is not the competition machine; performance and AVX2 guard behavior require serialized Linux x86 testing. No selected source was changed.

For ordinary unescaped names this candidate replaces the selected 32-byte AVX2 delimiter scan with an eight-byte fused scan. Consequently the native ARM screen cannot predict x86 performance. Independent review checked bounds of each unaligned load, the first-match property of the quote mask, escaped-pair fallback, empty-name hash equivalence and separation of compact and large-file fallback hashes. Equal full hashes still route to one owner; independently salted promotion limits the per-hash name lookup structure but does not redistribute that owner.

On an AVX2-capable x86-64-v3 Linux host with independently generated full seed-1 data, run tests and paired measurements serially:

```sh
rustc --edition=2021 -O -C lto=fat -C codegen-units=1 -C panic=abort -C target-cpu=x86-64-v3 experiments/c-fused-namehash/baseline.rs -o /tmp/c-fused-base
rustc --edition=2021 -O -C lto=fat -C codegen-units=1 -C panic=abort -C target-cpu=x86-64-v3 experiments/c-fused-namehash/candidate.rs -o /tmp/c-fused-candidate
python3 experiments/c-fused-namehash/property.py --avx2
python3 experiments/c-fused-namehash/guard.py --avx2
python3 experiments/c-fused-namehash/reference.py --source experiments/c-fused-namehash/candidate.rs --seeds 24 --avx2
python3 experiments/c-fused-namehash/edge.py --avx2
python3 experiments/c-fused-namehash/groups.py --avx2
python3 experiments/c-fused-namehash/collision.py --avx2
python3 experiments/c-fused-namehash/cut_oracle.py --avx2
python3 experiments/c-fused-namehash/gate.py
python3 experiments/c-fused-namehash/owner-property.py
python3 experiments/c-nameowned/compare.py --baseline /tmp/c-fused-base --variant /tmp/c-fused-candidate --data /path/to/full-c --runs 15 --report /tmp/c-fused-x86.json
```

Repeat timing, report native peak RSS and samples, and run official gates separately. The archive excludes datasets, credentials, and unrelated files.
