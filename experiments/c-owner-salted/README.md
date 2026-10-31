# Track C salted prehashed owner reduction — experimental, unselected

This package contains the exact current selected AVX/direct-country source as `selected.rs` (SHA-256 `3f72fb04f7ecde22e60e1bbb1b84e89e6e2bd3dba3bece03a4845db01a5dc68d`), the separately proposed eight-byte compact-owner comparator `baseline.rs` (`b199855d6c1155decd0c27a329e1a0515681c54011f1b5b11df7752172a3dae4`), and this candidate (`0aa4cbccf08b05a59aadbe7eaf23a931e468a95f76463a95100a142e8221bc08`). The selected source was not changed.

The candidate retains compact-owner's name-hash ownership, exact decoded-name reconstruction, per-owner bitmaps and pre-output fallback, but carries the 64-bit name hash with each event, increasing its `repr(C)` record from 8 to 16 bytes. The owner maps the full prehash through a standard randomized `HashMap<u64, ...>`; up to eight distinct names with the same full hash use an exact-byte chain, and the ninth promotes those row IDs to an independently randomized exact-name map. This mitigates the distinct-prehash clustering seen in the unseeded prototype while preserving exact equality and group bitsets. Randomized hashing is probabilistic, not a worst-case time guarantee: identical full Fx hashes still route to one owner and concentrated routing or long names can skew work. No data, cached answers, credentials or external dependencies are included.

Names with encoded length ≥65,535 use a sentinel and are reparsed from the live mmap without truncation. For file sizes greater than `u32::MAX` or group counts reaching the u16 sentinel, the original selected sharded algorithm is chosen before record processing and output creation. A real >4 GiB mapping has not been tested: exact arithmetic boundaries and full fallback with test-only reduced thresholds were verified. The parser relies on the official generated-input guarantees in §2.2 and §2.3, not unrestricted CSV grammar.

The exact candidate passed 24 mixed reference corpora at five worker counts, 357 CRLF/quoted-newline splits, 20 long-name/sentinel/forced-fallback references, 20 group-boundary references through all 17,576 possible country codes, 12 repeated-name/growth/forced-hash references, and 1,007,168 owner-range checks. `independent-collision.py` extracts the exact source and checks promotion at 8→9 equal-hash names, 50,000 forced equal-hash names with group bits through 512, duplicate/empty names and multiple promoted hashes; it also checks 16,384 artificially clustered distinct prehashes. Legal Fx name preimages for that synthetic cluster were not established. An independent reviewer found no defect in routing, full-byte equality, promotion, row IDs, bitmap preservation or fallback under §2.2/2.3; Linux/x86 execution remains outstanding.

One 15-pair native ARM batch against the 8-byte compact owner had median candidate/baseline wall 0.09172/0.09152 s and CPU 0.49990/0.50788 s; maximum process RSS was about 286/254 MB. A separate 15-pair batch versus selected had candidate/baseline wall 0.08883/0.10597 s and CPU 0.49566/0.67449 s; maximum native RSS about 285/226 MB. All 64 full outputs matched. These shared ARM batches do not establish x86 speed or official cgroup memory. The 16-byte event payload alone is 53.12 MB for 3.32 million rows, before capacity growth, maps and bitsets; actual target peak must be measured. Reports retain samples. No Mac Docker was used.

On a compatible x86-64-v3 Linux host, generate official full seed-1 data independently and run serialized:

```sh
rustc --edition=2021 -O -C lto=fat -C codegen-units=1 -C panic=abort -C target-cpu=x86-64-v3 experiments/c-owner-salted/selected.rs -o /tmp/c-salted-selected
rustc --edition=2021 -O -C lto=fat -C codegen-units=1 -C panic=abort -C target-cpu=x86-64-v3 experiments/c-owner-salted/baseline.rs -o /tmp/c-salted-compact
rustc --edition=2021 -O -C lto=fat -C codegen-units=1 -C panic=abort -C target-cpu=x86-64-v3 experiments/c-owner-salted/candidate.rs -o /tmp/c-salted-candidate
python3 experiments/c-owner-salted/gate.py
python3 experiments/c-owner-salted/owner-property.py
python3 experiments/c-owner-salted/independent-collision.py --avx2
python3 experiments/c-owner-salted/reference.py --avx2 --source experiments/c-owner-salted/candidate.rs --seeds 24
python3 experiments/c-owner-salted/edge.py --avx2
python3 experiments/c-owner-salted/groups.py --avx2
python3 experiments/c-owner-salted/collision.py --avx2
python3 experiments/c-owner-salted/cut_oracle.py --avx2
python3 experiments/c-nameowned/compare.py --baseline /tmp/c-salted-selected --variant /tmp/c-salted-candidate --data /path/to/generated-full-c --runs 15 --report /tmp/c-salted-selected.json
python3 experiments/c-nameowned/compare.py --baseline /tmp/c-salted-compact --variant /tmp/c-salted-candidate --data /path/to/generated-full-c --runs 15 --report /tmp/c-salted-compact.json
```

Repeat paired batches and retain individual samples. `--avx2` tests compile the x86-64-v3 path and require hardware support. Each comparison checks the public full hash; native RSS is not official warmed-cgroup peak, and official practice gates are separate.
