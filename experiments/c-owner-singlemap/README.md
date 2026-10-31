# Track C compact single-map owner — experimental

Baseline is exact selected salted-owner SHA-256 `0aa4cbccf08b05a59aadbe7eaf23a931e468a95f76463a95100a142e8221bc08`. Candidate is `0fb93cd5f5b66a740c516670f79314e6ca989260f6e5ba3b774bdba8ffa41910`. No selected source is changed.

For at most 256 total groups, each owner's salted prehash table directly stores the exact encoded name and four inline group words, avoiding a separate row and bit-vector lookup. If distinct names have the same full hash, the entry promotes to an independently salted exact-name map and retains all existing bits. Empty names compare by bytes as before. Inputs with more than 256 groups use the original owner table; the existing over-4-GiB and packed-representation gates select the original sharded fallback before processing and output. Equal full hashes still route to one owner; randomized maps are not a worst-case time guarantee.

The candidate passed 24 mixed corpora at five worker counts; 20 long-name/sentinel/forced-fallback cases; 20 lookup/group cases including all 17,576 country codes; 12 repeated-name and forced-hash-collision cases; 357 CRLF and quoted-newline cut/reference cases; and 1,007,168 owner properties. An overflow-checked 50,000-name collision test exercises all four words against a `HashSet` oracle. Independent source review found no defect in One-to-Many promotion, full-byte equality, empty names, preserved bits, group boundaries, or fallback; its separate test checks boundary bits across 0–255 and interacting colliding hashes. True >4-GiB full parsing and Linux AVX2 are untested.

Two shared ARM 15-pair full-data batches produced candidate/baseline median wall 0.11381/0.12613 s and 0.13106/0.18590 s; CPU 0.51862/0.53854 s and 0.53425/0.55948 s. All 64 outputs matched the published hash. The runs were heavily contended; wall ratios vary too much for a reliable speed estimate. Raw samples are `arm-report.json` and `arm-repeat.json`; no x86 or official result exists. `SmallRow` is 56 bytes on ARM before hashmap capacity/control overhead, so memory depends on cardinality and load; target native RSS and official cgroup peak require measurement.

For a serialized target check on an AVX2-capable x86-64-v3 Linux host, independently generate full seed-1 data and run:

```sh
rustc --edition=2021 -O -C lto=fat -C codegen-units=1 -C panic=abort -C target-cpu=x86-64-v3 experiments/c-owner-singlemap/baseline.rs -o /tmp/c-singlemap-base
rustc --edition=2021 -O -C lto=fat -C codegen-units=1 -C panic=abort -C target-cpu=x86-64-v3 experiments/c-owner-singlemap/candidate.rs -o /tmp/c-singlemap-candidate
python3 experiments/c-owner-singlemap/reference.py --source experiments/c-owner-singlemap/candidate.rs --seeds 24 --avx2
python3 experiments/c-owner-singlemap/edge.py --avx2
python3 experiments/c-owner-singlemap/groups.py --avx2
python3 experiments/c-owner-singlemap/collision.py --avx2
python3 experiments/c-owner-singlemap/cut_oracle.py --avx2
python3 experiments/c-owner-singlemap/stress.py --avx2
python3 experiments/c-owner-singlemap-review/run.py
python3 experiments/c-owner-singlemap/gate.py
python3 experiments/c-owner-singlemap/owner-property.py
python3 experiments/c-nameowned/compare.py --baseline /tmp/c-singlemap-base --variant /tmp/c-singlemap-candidate --data /path/to/full-c --runs 15 --report /tmp/c-singlemap-x86.json
```

Repeat paired timing, retain samples, and measure native RSS and official warmed-cgroup peak separately. This archive excludes datasets, credentials and unrelated files.
