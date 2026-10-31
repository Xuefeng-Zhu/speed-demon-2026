# Track C direct-mapped atomic name slots (experimental)

`baseline.rs` is the exact selected CRLF candidate, SHA-256 `3e181c76981348a96b48470844ee0f8988847d32164ff935a211024861c86ad4`. `candidate.rs` is SHA-256 `bd7e2d8a61201cfa50394eeb5683bbefe08b036b6b2cc55be190b0bfde7a4bb3`. Each name hashes to one of 2^18 fixed slots; the first name to claim a slot is an immutable borrowed key with atomic group bits. Equal names share that slot, while all other exact-byte names use the original sharded locked dictionary. Slots never change identity and are bounded; nodes persist until process exit. No data is recognized or precomputed. The original §2.2 CRLF guarantee remains required.

Two randomized native shared-Mac ARM warm-cache batches (9 and 11 measured pairs, one warmup each) matched every public full seed-1 output hash. Median wall candidate/baseline: 0.12830/0.14777 s then 0.11003/0.12718 s; CPU 0.75952/0.85632 s then 0.68202/0.82676 s. Max process RSS approximately 218.7/226.2 MB. These are noisy native ARM timings, not x86, scoring-box or cgroup measurements. Reports hold all samples. No Mac Docker was used. No selected source was changed.

`python3 experiments/c-rust-independent.py --source experiments/c-fastslot/candidate.rs --seeds 24` passed 120 reference comparisons. `python3 experiments/c-fastslot/collision.py` passed eight reference comparisons with 310 groups and normal or forced-constant hashes across 1/2/7/16 workers. `python3 experiments/c-fastslot/race.py` passed 108 repeated reference checks with 131,072 rows, 513 groups, empty/escaped names, 2/8/32 workers and normal, constant-hash or forced-one-slot variants. Its test variants enable Rust overflow checks. The independent `python3 experiments/c-fastslot/atomic_stress.py` runs the actual `fast_see` function with 2/8/32 threads, 68 names, 14 group bits through 309, one slot and identical hashes, four times each. `python3 experiments/c-fastslot/model.py` checked 63,360 sequentially consistent interleavings of three workers' atomic operations; it is a simple model, not a weak-memory checker or sanitizer. No Rust sanitizer was available in the local stable toolchain.

An independent review relayed by the parent found no correctness defect in Acquire/AcqRel slot publication, immutable name lifetimes, atomic fetch-or uniqueness, or exact fallback. Successful CAS publishes fully initialized node contents; losing CAS frees its unused node. A name can only follow the slot or fallback path consistently, because the slot never changes and equal input bytes have equal hashes. Every `(name, group)` first bit transition is atomic or protected by the existing shard mutex. At most 2^18 cache nodes plus at most one speculative node per concurrent insertion remain allocated, each with one atomic word per 64 groups; collided distinct names occupy the existing fallback dictionary. Input maps live for the process lifetime. This is a design review, not proof against every implementation or machine fault.

Run on a compatible x86-64-v3 Linux host, with Rust/Python and independently generated full seed-1 data, without concurrent benchmarks:

```
rustc --edition=2021 -O -C lto=fat -C codegen-units=1 -C panic=abort -C target-cpu=x86-64-v3 experiments/c-fastslot/baseline.rs -o /tmp/c-fastslot-base
rustc --edition=2021 -O -C lto=fat -C codegen-units=1 -C panic=abort -C target-cpu=x86-64-v3 experiments/c-fastslot/candidate.rs -o /tmp/c-fastslot-candidate
python3 experiments/c-rust-independent.py --source experiments/c-fastslot/candidate.rs --seeds 24
python3 experiments/c-fastslot/collision.py
python3 experiments/c-fastslot/race.py
python3 experiments/c-fastslot/atomic_stress.py
python3 experiments/c-fastslot/model.py
python3 experiments/c-nameowned/compare.py --baseline /tmp/c-fastslot-base --variant /tmp/c-fastslot-candidate --data /path/to/full-c --runs 15 --report /tmp/c-fastslot-x86.json
```

The comparator verifies the public hash every time and records wall, CPU and native process RSS; cgroup peak and official scoring remain separate. Execute repeated paired batches, record individual samples and compare cold behavior as relevant. Candidate promotion requires x86 results, full review and official practice gates. No credentials, datasets or precomputed answers are in this archive.

## Dot VM x86 result

The parent-run native x86 comparison regressed versus the exact baseline, so this candidate was not selected. Across this and four other packages, 272 full hashes, 40 alternate comparisons, AVX2/guard, collision and graph-oracle checks passed.
