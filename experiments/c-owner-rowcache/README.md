# Track C owner-local exact-name row cache

Experimental candidate, not selected. `baseline.rs` is the exact selected salted owner at SHA-256 `0aa4cbccf08b05a59aadbe7eaf23a931e468a95f76463a95100a142e8221bc08`; `candidate.rs` is `b22677746562473b49b241aed8f2b1302f3b5e924c3d3735d507eba19894bf22`. Each exclusive owner lazily allocates a 32,768-entry direct-mapped `(full hash, row ID)` cache. It skips the salted dictionary lookup only after checking both full hash and exact encoded-name bytes; misses retain the selected implementation's capped same-hash chains and salted promotion. Row IDs remain stable through vector growth and promotion; direct-slot conflicts affect performance only. Cache adds 512 KiB per active owner. Original >4 GiB and group-limit fallback is unchanged and chosen before processing/output; large true full-hash families still route to one owner as in baseline.

Independent diff review found no correctness defect in sentinel initialization, full-byte hit checks, ID stability, group bitsets or promotion. The exact candidate passed 24 mixed corpora x five worker counts; 20 long-name/sentinel/forced-fallback references; 20 group cases including all 17,576 countries; 12 forced collision and duplicate references; 357 record-boundary comparisons; 1,007,168 owner-range properties; and overflow-checked tests for 8,000 distinct prehashes colliding on one cache slot, 50,000 equal-hash names and promotion, and 100,000 random model operations. A separate independent 180,000-operation HashSet oracle exercised 600 equal-hash names, 513 groups, growth, promotion and repeat hits at both one and 32,768 cache slots. Actual Linux AVX2 execution, full parsing of actual >4 GiB files, cgroup memory and x86 timing remain unverified.

Two 32K cache ARM native paired batches (9 and 15 measured pairs with a warmup each) showed median wall candidate/baseline 0.09571/0.10236 s and 0.09078/0.09959 s; CPU 0.4813/0.5177 s and 0.4740/0.5162 s. Full output hashes matched in all 52 executions. These are shared-Mac measurements, not target/official results. Raw samples are `cache32768.json` and `cache32768-repeat.json`. Run serialized x86 comparisons and measure peak memory before any selection.

The following commands use independently generated full seed-1 data, a capable x86-64-v3 Linux machine and a serialized benchmark. No dataset or credentials are included.

```sh
rustc --edition=2021 -O -C lto=fat -C codegen-units=1 -C panic=abort -C target-cpu=x86-64-v3 experiments/c-owner-rowcache/baseline.rs -o /tmp/c-rowcache-base
rustc --edition=2021 -O -C lto=fat -C codegen-units=1 -C panic=abort -C target-cpu=x86-64-v3 experiments/c-owner-rowcache/candidate.rs -o /tmp/c-rowcache-candidate
python3 experiments/c-owner-rowcache/reference.py --source experiments/c-owner-rowcache/candidate.rs --seeds 24 --avx2
python3 experiments/c-owner-rowcache/edge.py --avx2
python3 experiments/c-owner-rowcache/groups.py --avx2
python3 experiments/c-owner-rowcache/collision.py --avx2
python3 experiments/c-owner-rowcache/cut_oracle.py --avx2
python3 experiments/c-owner-rowcache/independent-collision.py --avx2
python3 experiments/c-owner-rowcache/cache-test.py --avx2
python3 experiments/c-owner-rowcache/gate.py
python3 experiments/c-owner-rowcache/owner-property.py
python3 experiments/c-rowcache-independent/run.py
python3 experiments/c-nameowned/compare.py --baseline /tmp/c-rowcache-base --variant /tmp/c-rowcache-candidate --data /path/to/full-c --runs 15 --report /tmp/c-rowcache-x86.json
```

Repeat the paired timing batch and retain full samples and peak native RSS; official warmed-cgroup memory and practice validation are separate.
