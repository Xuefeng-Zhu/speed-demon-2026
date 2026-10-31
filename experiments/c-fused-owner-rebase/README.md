# C owner dictionary alternatives on fused-name baseline (unselected)

`baseline.rs` is the selected fused-name implementation, SHA-256 `6e12627e96f0a0433e567413ccacc1a5d7fdf2de8f4781a3f826c260499783dd`. `rowcache.rs` has SHA-256 `76b341e2b7e880fe4ceeee220206a63b48cd247bba4448aa7991a7ad825e8dd2`. It adds a lazily initialized 32,768-entry direct-mapped owner-local cache of `(full prehash, stable row index)`. A hit must compare the stored full hash and exact name bytes; a miss uses the selected bounded collision chains and salted promotion. Equal full hashes still route to one owner; no worst-case time guarantee is claimed. Each active owner adds 512 KiB on 64-bit systems. The fallback for file lengths greater than u32 and the group-representation limit is unchanged.

This is a rebase of `experiments/c-owner-rowcache/` onto the current fused parser, with no change to the parser. `singlemap.rs` is the corresponding rebase of `experiments/c-owner-singlemap/`; it is retained for comparison but the ARM screen below is inconsistent, so it is not the candidate for target testing. Neither source has been selected or submitted.

Each rebased source passed 24 mixed corpora at 1, 2, 3, 7 and 16 workers against the official reference, plus eight such corpora with the name prehash forced to zero. The rowcache passed overflow-checked tests for same-slot collisions, full-hash promotion and reallocation, randomized model operations, and an independent stress tail at both one and 32,768 cache slots. The singlemap passed its overflow-checked collision and all-four-group-word stress test. An independent review found no defect and an additional 8-million-operation HashSet oracle passed; see `experiments/c-rowcache-independent/README.md`. Actual x86 AVX2 execution, true >4 GiB full parsing and target cgroup use remain untested.

On shared native ARM using generated full public seed 1, randomized 15-pair warmed runs had rowcache baseline/candidate median wall seconds `0.077037/0.072239`, `0.085199/0.080629`, `0.084617/0.077989`; median CPU seconds `0.457404/0.428194`, `0.466977/0.440125`, `0.474466/0.437683`. Median process RSS was approximately 270/274 MiB. A diagnostic compile may have overlapped the first batch; the latter two batches were serialized, though the host remains shared. The singlemap's two paired median walls were `0.086865/0.076370` and `0.084683/0.086546`, with CPU `0.465638/0.474077` and `0.479786/0.470035`, respectively. All 160 measured and warmup outputs across the five batches matched the public full-data SHA-256. Raw samples are in the `*-arm*.json` files. Native ARM results do not imply x86 or official speed.

For an x86-64-v3 Linux check, extract the archive at its root. The archive must contain this directory, `experiments/c-rowcache-independent/{README.md,run.py,test-tail.rs}` and `official/reference/c_join.py`; generate the full seed-1 dataset independently. It contains no dataset or credentials. Serialize timing and verify hardware support before `--avx2`:

```
python3 experiments/c-fused-owner-rebase/verify.py --avx2
python3 experiments/c-rowcache-independent/run.py
rustc --edition=2021 -O -C lto=fat -C codegen-units=1 -C panic=abort -C target-cpu=x86-64-v3 experiments/c-fused-owner-rebase/baseline.rs -o /tmp/c-rebase-base
rustc --edition=2021 -O -C lto=fat -C codegen-units=1 -C panic=abort -C target-cpu=x86-64-v3 experiments/c-fused-owner-rebase/rowcache.rs -o /tmp/c-rebase-rowcache
python3 experiments/c-fused-owner-rebase/compare.py --baseline /tmp/c-rebase-base --variant /tmp/c-rebase-rowcache --data /path/to/full-c --runs 15 --report /tmp/c-rowcache-x86.json
```

Repeat the paired measurement and separately inspect native RSS and official cgroup peak. Hidden-seed correctness and official performance are not established by this package.
