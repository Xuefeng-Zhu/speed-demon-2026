# Track B inline short-key comparison

This archive contains source and correctness tools only; no data, credentials, binaries, or precomputed answers. The baseline is the selected short-token table implementation at the time of packaging (source SHA-256 `d0f0d79f3f646275d2e33ef34659eba5bca56fb2bb16504025f10a800e88cc49`); candidate SHA-256 `2c85df365cccdac96797dfe330814f8d04cb2e8ea9684cc8f5175aa6726c4d1b` stores each short key inline with its ID. Full-key equality and sentinel-ID empties preserve correctness; phrase and bitmap code are unchanged. Each short slot occupies 16 bytes on 64-bit systems rather than four; documented worst-case 338,000 short terms require 1,048,576 slots, 16 MiB payload, not total RSS.

On an AVX2-capable x86-64 Linux VM, generate the official full seed-1 data independently. From this archive root:

```sh
rustc --edition=2021 -O -C lto=fat -C codegen-units=1 -C panic=abort -C target-cpu=x86-64-v3 experiments/b-inline-short/baseline.rs -o /tmp/b-inline-baseline
rustc --edition=2021 -O -C lto=fat -C codegen-units=1 -C panic=abort -C target-cpu=x86-64-v3 experiments/b-inline-short/candidate.rs -o /tmp/b-inline-candidate
rustc --edition=2021 --test -C opt-level=2 -C overflow-checks=yes experiments/b-inline-short/b-inline-review-property.rs -o /tmp/b-inline-property && /tmp/b-inline-property
rustc --edition=2021 --test -C opt-level=2 -C overflow-checks=yes experiments/b-inline-short/b-inline-review-forced.rs -o /tmp/b-inline-forced && /tmp/b-inline-forced
python3 experiments/b-short-lookup/independent-review.py /tmp/b-inline-candidate
export B_RUST_BINARY=/tmp/b-inline-candidate
python3 experiments/b-bounded-fuzz.py "$PWD/experiments/b-rust-positional-adapter.py"
python3 experiments/b-bounded-shards.py "$PWD/experiments/b-rust-positional-adapter.py"
python3 experiments/b-bounded-boundary.py "$PWD/experiments/b-rust-positional-adapter.py"
python3 experiments/b-bounded-duplicates.py "$PWD/experiments/b-rust-positional-adapter.py"
python3 experiments/b-inline-short/compare.py --baseline /tmp/b-inline-baseline --candidate /tmp/b-inline-candidate --data /path/to/full-b --runs 9 --report /tmp/b-inline-results.json
```

The 90 independent corpora test empty/short-free, token lengths, prefixes, uppercase and UTF-8; the normal and forced-zero-hash Rust property tests exercise collision behavior. Both candidates include the previously independently tested AVX2 classifier unchanged; additionally run the established AVX2 guard-page and classifier tests if that environment or compiler differs. The comparator warms both, randomizes paired order, checks every published hash and records native process RSS, which is not cgroup memory. Benchmark serialized without other heavy jobs.

Two noisy native shared-Mac ARM scalar-path screens measured candidate/baseline medians 0.25896/0.26501 s across 9 pairs and 0.25662/0.26610 s across 15 pairs. All full hashes, 40 mixed reference corpora, shard and >1 MiB boundary checks passed. The independent reviewer found no defect; 90 reference corpora and normal/forced-collision property tests passed. The x86 AVX2 path and target cgroup behavior of this changed binary remain unverified; do not infer official scoring from ARM timing.

Subsequent serialized x86 dot VM testing found inline short keys 1.2–2.1% slower in two paired passes. The worker sweep measured auto nine workers at 0.302 s versus 0.331 s at eight and 0.347 s at twelve in its repeat. Across the campaign 136 full hashes, 12 alternate references, AVX2, collision and property stress checks passed. Exact samples were not supplied here. VM worker and process-memory observations do not establish the optimum on the scoring box; the existing implementation remains selected.
