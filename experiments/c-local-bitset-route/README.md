# C parser-local name/group bitsets (unselected)

This isolated experiment is based on exact selected dual-lane C `baseline.rs` SHA-256 `8249f318e26050cc1a12f2be091344bf431ceb862665a3312bb29a92e140057d`; `candidate.rs` SHA-256 is `fb4d7ca03e49571aa7a6d03db26d67c3cd387458bdf86a453d2604dfbd066248`. Selected code was not changed.

Each parser uses the existing exact `OwnerDict` and group bitsets while parsing, instead of emitting an event for every record. At the end of parsing it routes each locally unique name once by its recomputed full hash; reducer workers OR that local row's group words into an exact owner dictionary and count newly set group bits. Equal raw encoded names have the same name hash and owner; the owner maps and local maps retain exact-byte checks and existing full-hash collision promotion. The >4 GiB/group-gate fallback is unchanged. The optimization relies on the same §2.2 generated-input CRLF guarantee as the baseline.

The candidate's compact event struct and `event_name` function are now unused and produce dead-code warnings. This unselected experiment was not cleaned for submission, independently reviewed, checked on x86/AVX2, or run on complete >4 GiB input. It is not a general unrestricted CSV implementation.

## Checks

A native ARM `-O -C overflow-checks=yes -C debug-assertions=yes` build succeeded. The exact candidate passed `experiments/c-fused-owner-rebase/reference.py --source experiments/c-local-bitset-route/candidate.rs --seeds 24` (120 comparisons); `groups.py` (9 group counts 1/63/64/65/240/241/256/257/17576 × 5 workers, duplicate groups and names, escaped/empty names and lengths 65534–65536); `forced-collision.py` (both producer hash sites, tail site and row-routing hash forced to zero, exact output and collision-promotion marker across 5 workers); and `forced-fallback.py` (both pre-output gates across 5 workers). Their raw output and compiler warnings are in `checks.log`. These finite cases do not establish all hidden-input correctness, memory, cgroup or Linux x86 behavior.

## Native ARM performance and memory

A randomized 9-pair full seed-1 comparison plus warmup checked all 20 output hashes. Median wall was **0.156768 s candidate versus 0.066011 s selected** (~137.5% slower); CPU was 0.992263 versus 0.402014 s. Maximum process RSS in measured runs was 333,086,720 versus 294,879,232 bytes; process RSS and shared-host ARM timings are not official cgroup or x86 scores. Raw timings are `arm-a.json`. The regression is large enough that no repeat or target-machine recommendation is justified.

At `N` records and `W` group bitset words, local and final dictionaries together can retain up to roughly `N*(60+16*W)` bytes of logical entry, group-bit, hash, and row-ID payload, before HashMap slots, collision-promotion tables, spare Vec capacity, allocator retention, input mapping, threads, and kernel charges. This is only component arithmetic, not an 8 GiB cgroup proof. For full's 3,320,000 records and 241 active groups (`W=4`), that component is about 412 MB; wider defensive group counts make it substantially larger. The number of names is not assumed to follow the planning distribution.

Reproduce only in a serialized CPU window using identical release flags and a separately generated or verified full seed-1 dataset:

```sh
python3 experiments/c-fused-owner-rebase/reference.py --source experiments/c-local-bitset-route/candidate.rs --seeds 24
python3 experiments/c-local-bitset-route/groups.py
python3 experiments/c-local-bitset-route/forced-collision.py
python3 experiments/c-local-bitset-route/forced-fallback.py
rustc --edition=2021 -O -C lto=fat -C codegen-units=1 -C panic=abort experiments/c-local-bitset-route/baseline.rs -o /tmp/c-local-baseline
rustc --edition=2021 -O -C lto=fat -C codegen-units=1 -C panic=abort experiments/c-local-bitset-route/candidate.rs -o /tmp/c-local-candidate
python3 experiments/c-fused-owner-rebase/compare.py --baseline /tmp/c-local-baseline --variant /tmp/c-local-candidate --data /path/to/full-c --runs 9 --report /tmp/c-local-report.json
```

The pre-existing `/tmp/sdc-full` dataset was verified against both official input hashes and was neither changed nor removed. No Mac Docker was used.
