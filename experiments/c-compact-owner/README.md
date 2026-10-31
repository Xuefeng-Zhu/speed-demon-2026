# C compact owner reduction — experimental and unselected

`baseline.rs` is the exact current selected AVX/direct-country source SHA-256 `3f72fb04f7ecde22e60e1bbb1b84e89e6e2bd3dba3bece03a4845db01a5dc68d`; `candidate.rs` is `b199855d6c1155decd0c27a329e1a0515681c54011f1b5b11df7752172a3dae4`. Each parser records an eight-byte `(u32 file offset, u16 encoded-name length, u16 group)` event in a name-hash owner bin. Reducers then build private exact-byte name maps and group bitsets; equal names route to the same owner and hash collisions compare full bytes. Numeric aggregates remain per parser. Owner selection uses multiply-high into exactly the worker count to avoid bucket-count skew; concentrated name hashes can still overload one owner.

Encoded lengths at or above 65,535 use a sentinel and reparse the original mmap slice with the existing quote-aware parser; nothing is truncated. The selected original sharded implementation is chosen **before parsing or creating output** if the input mapping exceeds `u32::MAX` bytes or group count reaches the `u16` sentinel. Generated lookup data is restricted to three-uppercase-letter country codes by §2.3, so it has at most 17,576 groups, but the group gate is still checked. The record parser, raw-name equality and chunk boundaries retain the official §2.2 assumptions; this is not unrestricted CSV §2.1 support. No fixed answers, input recognition, datasets or credentials are included.

The exact rebased candidate passed the public full hash; 24 mixed corpora at five worker counts; 357 CRLF/quoted-newline split cases; 20 long-name/sentinel, forced-route/full-hash collision, and test-only forced pre-output fallback checks; 20 group/lookup cases through all 17,576 codes; 12 repeated-name and full-hash collision-growth reference checks; 1,007,168 owner-range checks; and independent exact-source sentinel/offset/owner partition unit tests. The long-field wrapper raises Python csv's default field-size limit but uses the same official reference logic. The gate test exercises 4 GiB and group boundaries arithmetically, and lowered thresholds exercise both full fallback branches. **A real >4 GiB mmap was not run.** Tests use valid §2.2 data unless explicitly described as stress or defensive extensions.

Independent review found no defect in bounds, sentinel reconstruction, owner routing, full-byte collision handling or fallback placement under the stated guarantees. A name is always one subslice of the live mmap; reducers join before it can be dropped. Equal names deterministically share an owner and only that reducer mutates their bitmap. On official full shape the packed event payload is 3.32 million × 8 bytes (26.56 MB), plus Vec capacity growth, per-worker bins, exact maps and bitsets. A larger-than-4-GiB input uses the baseline; individual names have no fixed bound and long ones incur reparsing. Adversarial equal hash distributions or very long names can skew work or induce collision costs. Actual x86 cgroup peak and throughput must be measured before promotion.

On a shared ARM Mac, 15 randomized full-seed pairs of the exact rebased source, after warmup, gave candidate/baseline median wall 0.08947/0.10394 s, CPU 0.50361/0.65541 s and max process RSS roughly 253/226 MB; every output matched. Earlier two 15-pair screens against the pre-AVX source were 0.08442/0.10358 and 0.08641/0.10619 s, with a test compile overlapping the first; those are only supporting ARM fallback evidence. None of these is an x86 or official score; the prior older name-owned architecture had inconsistent target results. Raw JSON retains samples. No Mac Docker was used.

On a compatible x86-64-v3 Linux host, generate official full seed-1 data separately and run **serialized**, with no competing benchmarks:

```sh
rustc --edition=2021 -O -C lto=fat -C codegen-units=1 -C panic=abort -C target-cpu=x86-64-v3 experiments/c-compact-owner/baseline.rs -o /tmp/c-owner-base
rustc --edition=2021 -O -C lto=fat -C codegen-units=1 -C panic=abort -C target-cpu=x86-64-v3 experiments/c-compact-owner/candidate.rs -o /tmp/c-owner-candidate
python3 experiments/c-compact-owner/gate.py
python3 experiments/c-compact-owner/owner-property.py
python3 experiments/c-compact-owner/independent.py --avx2
python3 experiments/c-compact-owner/reference.py --avx2 --source experiments/c-compact-owner/candidate.rs --seeds 24
python3 experiments/c-compact-owner/edge.py --avx2
python3 experiments/c-compact-owner/groups.py --avx2
python3 experiments/c-compact-owner/collision.py --avx2
python3 experiments/c-compact-owner/cut_oracle.py --avx2
python3 experiments/c-nameowned/compare.py --baseline /tmp/c-owner-base --variant /tmp/c-owner-candidate --data /path/to/generated-full-c --runs 15 --report /tmp/c-owner-x86.json
```

Repeat paired batches, validate every public hash, and record wall, CPU and process RSS. Tests with `--avx2` compile x86-64-v3 and require host support. Process RSS is not official warmed-cgroup peak; official practice gates and memory are separate. No selected code is changed by this experiment.
