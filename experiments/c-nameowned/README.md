# Track C name-owned distinct aggregation

The commands below apply to the separate Library transfer archive. In the repository, run `python3 experiments/c-nameowned/independent.py` for the independent 130-group reference test and `python3 experiments/c-nameowned/multigroup.py experiments/c-nameowned/candidate.rs official/reference/c_join.py` for the 240-group test.

Baseline is exact selected CRLF source at `4f2d688` SHA-256 `3e181c76981348a96b48470844ee0f8988847d32164ff935a211024861c86ad4`. Candidate SHA-256 `5b4b34ea0e279750e3ca97c1114f4499bcec4a27ddf8a520a5d4fa1687fa1b9f` partitions name/group views by exact name hash while parsing, then a separate owner per hash shard deduplicates full-byte names and group bitsets without shared dictionary locks. It preserves the CRLF synchronization guarantee of official §2.2 (not broader §2.1 alone). It computes all outputs from input and has no external dependencies. `forced.rs` forces all hashes equal solely for correctness tests; it is not a performance candidate.

Generate full seed-1 data separately with the official generator; no dataset is included. On a compatible x86-64-v3 host and Rust/Python, from this directory:

```
rustc --edition=2021 -O -C lto=fat -C codegen-units=1 -C panic=abort -C target-cpu=x86-64-v3 baseline.rs -o /tmp/c-nameowner-base
rustc --edition=2021 -O -C lto=fat -C codegen-units=1 -C panic=abort -C target-cpu=x86-64-v3 candidate.rs -o /tmp/c-nameowner-candidate
python3 compare.py --baseline /tmp/c-nameowner-base --variant /tmp/c-nameowner-candidate --data /path/to/full-c --runs 9 --report /tmp/c-nameowner-x86.json
python3 tests/reference.py --source candidate.rs --seeds 24
python3 tests/reference.py --source forced.rs --seeds 24
python3 tests/multigroup.py candidate.rs official/reference/c_join.py
python3 tests/independent.py
```

The comparator randomizes order, warms both, verifies every published output SHA-256, and records elapsed wall, CPU and wait4 process RSS. Linux RSS is KiB and not official cgroup memory. Run without other load and report individual samples, compiler, CPU count, and max RSS. Input prewarming and official cgroup peak need separate measurement.

Shared macOS ARM screens (heavy contention possible) matched every full hash. The initial five-pair medians were 0.1876 s candidate vs 0.4143 s baseline (CPU 0.7575 vs 1.1910); nine-pair repeat 0.1451 vs 0.1707 (CPU 0.7570 vs 0.9994). A further five-pair screen after removing unused code measured 0.1317 vs 0.2858 (CPU 0.6432 vs 0.9157). Native process RSS was approximately 316–322 MB candidate vs 226 MB baseline and includes mapped input; these figures are not official/x86 scores.

The cleaned candidate passed 24 mixed reference corpora at five worker counts for both ordinary and forced-zero hashing (240 total comparisons). A separate 240-country test passed normal and forced collisions across six counts, plus independent overflow-checked 30k-record/130-country+unmatched reference cases across four counts. Independent review found no issue under §2.2; exact target runtime, cgroup and source-size effects require measurement.

Two dot VM paired batches did not establish a stable speed win: the candidate was 19.3% faster in the first and 4.1% slower in the second, with approximately 35% higher process RSS. Across the C/B campaign all 112 full hashes and 16 alternate references passed, along with C collision stress. These are native VM results, not official cgroup scores; the CRLF baseline remains selected.
