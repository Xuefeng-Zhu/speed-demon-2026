# C bounded coarse owner pipeline (unselected)

`baseline.rs` is exact selected dynamic-owner C source SHA-256 `bcd4d7715bffd8a3dc062cad6e7aa0886a96d659fcc9170735c4d4d123f67eae`. `candidate.rs` has SHA-256 `7cf4d8ed20fad829a1963022529589d5cdaa6cbb88bc0e17a1223ec909e223c1` and caps workers at 12, splits the input into four times as many CRLF-aligned chunks, and assigns each chunk once through an atomic counter. Up to 12 parser workers route exact-name events by full hash to up to 12 dedicated owner workers. Each owner owns its dictionary and group counts; no dictionary is shared. This differs from selected 4n dynamically claimed owner partitions and the earlier same-worker cooperative 256-event queue experiment.

Each parser sends messages of at most 4,096 events through a `sync_channel` with two-message capacity per owner, flushing partial messages at each chunk end. Owner workers only receive, so the blocking channel graph has no sender/receiver cycle. Original sender handles are dropped after parser creation; parser clones close on normal return or unwind. Receivers drain until all senders are dropped. Scope unwind and join propagate panics before output is created. Thread startup or panic failure ends the run; it does not try to recover partial output.

The maximum *logical in-flight initialized event payload* with n <= 12 is `(n*n + 2*n + n) * 4096 * 16` = 11,796,480 bytes: parser-held bins, queued messages and one batch per owner. This is not a formal whole-process or cgroup memory bound: Vec capacity/allocator overhead and retention, dictionaries, mapped inputs, stacks and kernel charges remain. Equal full hashes can still concentrate all work on one owner. The >4 GiB/group-gate fallback remains the existing shard implementation. Chunk cuts reuse an earlier CRLF boundary when a later desired cut lies before it, avoiding repeated scans; the assumptions remain the official §2.2 generated-data contract.

Validation: an overflow/debug compile succeeded. A test-only worker-count substitution ran four hostile corpora at 1, 2, 3, 7 and 16 workers against the official reference (20 comparisons). `liveness.py` builds exact-source transformations with rendezvous channels, four-event messages and a forced single hash owner. It passed the normal reference comparison and injected parent panics during owner creation and parser creation, plus owner and parser panics, all without hangs or output. These are simulated panic points, not real OS thread-spawn failures or an exhaustive scheduler proof. An initial test-harness assertion failed because an injection needle occurred in both compact and fallback loops; after constraining the injection to the compact loop, all five cases passed. No Mac Docker was used.

A preliminary three-pair randomized native ARM full seed-1 screen after warmup matched every official output hash. Median candidate/baseline wall was 0.073180/0.065794 s (~11.2% slower); CPU was 0.507909/0.424400 s (~19.7% higher); native peak RSS was roughly 231/298 MB. The candidate has lower process RSS but loses on the explicit speed priority. Only three pairs were run on a shared host; there are no actual Linux/x86, official cgroup, large-file full parse or holdout measurements. Raw results are `arm-screen.json`. Do not promote or infer a target result from this screen.

Reproduce after generating the official full seed-1 input independently:

```sh
python3 experiments/c-coarse-owner-pipeline/liveness.py
rustc --edition=2021 -O -C lto=fat -C codegen-units=1 -C panic=abort experiments/c-coarse-owner-pipeline/baseline.rs -o /tmp/c-coarse-base
rustc --edition=2021 -O -C lto=fat -C codegen-units=1 -C panic=abort experiments/c-coarse-owner-pipeline/candidate.rs -o /tmp/c-coarse-candidate
python3 experiments/c-coarse-owner-pipeline/compare.py --baseline /tmp/c-coarse-base --variant /tmp/c-coarse-candidate --data /path/to/full-c --runs 3 --report /tmp/c-coarse-report.json
```
