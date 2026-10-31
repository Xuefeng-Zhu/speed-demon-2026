# B bounded two-level displaced short-token lookup (unselected)

`baseline.rs` is the exact selected B source, SHA-256 `7d371fe84ce9f0fd9d3c7e6fdf02b6b37e0f1440319c654161b990cf27bb8bf3`. `candidate.rs` is `16a18a370ebf2646e328a9ee2731a5b8306129d4eb9e0285e1d7a421b8e1602f`. It derives a bucket-displacement table from the actual query vocabulary, storing each zero-padded exact short key and its term ID together. Every lookup verifies the entire key. Long terms continue using the original exact dictionary; original postings, bounded phrase summaries and 64 MiB bitmap payload cap are unchanged. No corpus results are stored.

The existing short table is built first and remains the fallback. Construction is attempted only for at most 262,144 short terms; any bucket larger than 32 keys, failure to place a bucket within 256 displacement attempts, or exhaustion of the global `min(64*count,4,000,000)` placement-probe budget leaves the displacement table empty and uses the exact original table. The per-bucket cap also bounds the linear duplicate-position scan, though the total upper bound remains large and neither this nor the requested table-payload cap proves a whole-process cgroup maximum. The displaced table payload is at most 8 MiB at the supported maximum on the observed 64-bit Rust layout, plus bucket vectors, original table, allocator and runtime overhead. Reset-before-build protects a potential future rebuild. A difficult valid query vocabulary may fall back and spend extra construction work; sampling does not decide correctness.

An independent source review found no concrete lookup, placement, empty-dictionary or fallback defect; its same-primary adversarial-work and future-rebuild findings were addressed by the bucket cap and explicit reset. The exact corrected candidate passed `verify.py` on native ARM with overflow checks: exhaustive 47,988 one-to-three-byte keys and uppercase, absent words, successful build followed by a 33-keys-in-one-bucket failed rebuild, valid-token lookups at 262,144 and 262,145 count boundaries, 40 reference corpora with a forced zero budget and 40 with all hashes forced equal. In addition, the ordinary build passed 40 mixed reference corpora, 90 independent corpora, distributed top-ten/duplicate phrases, six >1 MiB documents, and 250,000-document/19,000-identical-phrase stress. The Linux-specific protected-page property in `property-tail.rs` is included but was not run on ARM/macOS.

Native shared-Mac ARM full public seed-1 measurements, 11 randomized paired runs plus warmups of the exact corrected candidate, gave candidate/baseline median wall **0.236997/0.244616 s** and CPU **1.427633/1.522118 s**; all 24 outputs matched published hash `f86973c210228141bcb6f1f1b10188ad2a9b65f71e7cd7cf4590b38de4e80927`. Before the cap/reset correction, two initial screens also favored the candidate, but those are not measurements of the final source. ARM uses the scalar classifier; x86 AVX2, Linux guard pages, official PGO interaction, cgroup peak and target performance remain untested. See raw JSON; an additional post-correction instrumented run confirmed activation on 49,402 short terms, 16,384 buckets and 131,072 slots, with the official full hash. Instrumentation is not timing evidence.

## Serialized x86 plan

Generate the official public full seed independently; do not include it in the transfer. On a free x86-64-v3 machine with an available Rust compiler, compile the two files with identical flags and run `python3 experiments/b-displaced-short25/verify.py` (its Linux test executes actual guard pages). Then run:

```
rustc --edition=2021 -O -C lto=fat -C codegen-units=1 -C panic=abort -C target-cpu=x86-64-v3 experiments/b-displaced-short25/baseline.rs -o /tmp/b-displaced-base
rustc --edition=2021 -O -C lto=fat -C codegen-units=1 -C panic=abort -C target-cpu=x86-64-v3 experiments/b-displaced-short25/candidate.rs -o /tmp/b-displaced-candidate
python3 experiments/b-short-lookup/independent-review.py /tmp/b-displaced-candidate
B_RUST_BINARY=/tmp/b-displaced-candidate python3 experiments/b-bounded-shards.py experiments/b-rust-positional-adapter.py
B_RUST_BINARY=/tmp/b-displaced-candidate python3 experiments/b-bounded-boundary.py experiments/b-rust-positional-adapter.py
B_RUST_BINARY=/tmp/b-displaced-candidate python3 experiments/b-bounded-duplicates.py experiments/b-rust-positional-adapter.py
python3 experiments/b-rust-lengthhash/compare.py --baseline /tmp/b-displaced-base --candidate /tmp/b-displaced-candidate --data /path/to/full-b --runs 15 --report /tmp/b-displaced-x86-a.json
python3 experiments/b-rust-lengthhash/compare.py --baseline /tmp/b-displaced-base --candidate /tmp/b-displaced-candidate --data /path/to/full-b --runs 15 --report /tmp/b-displaced-x86-b.json
```

Compare every full hash, CPU and native RSS in both paired batches. The actual official build uses PGO, so a native unprofiled win alone cannot establish an official win. Run the official practice only after independent review of the exact tested source, actual guarded x86 execution and the memory tradeoffs. Do not run Docker on the Mac.
