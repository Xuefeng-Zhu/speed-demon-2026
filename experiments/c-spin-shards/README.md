# C spin-sharded dictionary experiment — unselected

Baseline is the exact selected Track C source SHA-256 `3e181c76981348a96b48470844ee0f8988847d32164ff935a211024861c86ad4`; candidate SHA-256 is `007102c0a1d28fe21768c71d6be5a983c4f03943bec884ae0c8e50f47d083bd9`. The candidate replaces the 1,024 standard `Mutex` shard locks with a custom compare-exchange Acquire/Release lock. It spins up to 64 failed attempts, then yields; protected dictionary and parsing are unchanged. No data, credentials or answer caches are included. It relies on official §2.2 generated-input CRLF/name guarantees like the selected code.

**Risks:** The lock offers no fairness or starvation guarantee; yielding is not a bound on waiting. Oversubscription, hash/skew collisions or a descheduled lock owner may cause long waits and excess CPU. It does not implement standard Mutex poisoning: a caught panic releases the guard and another thread can observe data modified before the panic. The competition release build uses aborting panics, but this is still a behavioral difference. The standard library mutex on Linux uses a different implementation than the macOS timing host; lock semantics, worst-case scheduling, CPU, memory and official sandbox behavior require separate evaluation. Do not select solely from these results.

The initial independent review found a generic guard auto-trait issue: a guard could be `Sync` for a `Send`/`!Sync` value. That was fixed by adding `PhantomData<Cell<T>>` to make the exact candidate guard `!Sync`. A second independent review found no further memory-ordering or current call-site defect; the included `review.py` extracts the exact guard and checks the negative auto-trait property, successful Send, 1/2/7/32-thread increments, same-thread panic unwinding, and a blocked waiter acquiring after owner panic. In macOS runs a 32-worker maximum observed wait ranged from about 1.5 to 20.1 ms for spin versus about 0.9 to 2.5 ms for std, with variable totals. This is not a fairness proof. `review-report.txt` records one actual run; timeouts prevent an indefinitely hung test.

The exact fixed source passed 24 mixed corpora at five worker counts against the official reference and 96 full-program executions with all names forced onto one shard and either normal hash or constant hash, for one repeated name or 257 distinct names, at 1/2/7/32 workers. `stress.py` generates these 20,000-row data sets, randomizes paired baseline/candidate order, compares outputs byte for byte and imposes 45 seconds per execution as a no-progress timeout. This limited stress does not prove starvation freedom. `stress-report.json` retains individual timings; synthetic microsecond-level timings and shared host contention are not authoritative.

Two randomized 15-pair full-seed ARM Mac screens of the exact fixed candidate (plus warmups) passed all 64 output hashes. Candidate/baseline medians: 0.12057/0.14015 s and 0.13324/0.17235 s wall, 0.66048/0.81962 s and 0.65602/0.86250 s CPU. `arm-fixed.json` and `arm-fixed-repeat.json` contain samples. This is native macOS only, not Linux, x86, cgroup or official scoring; earlier pre-fix runs are retained only as historical context. No Mac Docker was run.

From the transfer archive root, generate official full seed 1 data separately and run serialized with Rust and Python installed:

```sh
rustc --edition=2021 -O -C lto=fat -C codegen-units=1 -C panic=abort -C target-cpu=x86-64-v3 experiments/c-spin-shards/baseline.rs -o /tmp/c-spin-base
rustc --edition=2021 -O -C lto=fat -C codegen-units=1 -C panic=abort -C target-cpu=x86-64-v3 experiments/c-spin-shards/candidate.rs -o /tmp/c-spin-candidate
python3 experiments/c-spin-shards/review.py
python3 experiments/c-rust-independent.py --source experiments/c-spin-shards/candidate.rs --seeds 24
python3 experiments/c-spin-shards/stress.py
python3 experiments/c-nameowned/compare.py --baseline /tmp/c-spin-base --variant /tmp/c-spin-candidate --data /path/to/generated-full-c --runs 15 --report /tmp/c-spin-x86.json
```

Run at least two paired batches. Each validates the full public hash and records elapsed, CPU and process RSS, not cgroup memory. Report worst-case stress wall, no-progress timeouts, actual x86 timings, and any errors separately. Official board gates and cgroup peak remain separate checks.
