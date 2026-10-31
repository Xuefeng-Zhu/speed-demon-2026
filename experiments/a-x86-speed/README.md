# Track A x86 speed work: paired benchmark harness and A/A noise

Local x86 VM measurements only. These are not official scores and were not taken on the scoring
box (i5-13500, 12 threads). They exist so that every Track A change on branch `a-x86-speed` is
measured the same way against the immediately prior source.

## Host

Shared KVM VM, Intel Xeon Platinum 8488C, 8 vCPUs (4 cores x 2 HT), AVX2, kernel 6.1,
rustc 1.92, python 3.11. Input is the full seed-1 dataset (238,836,234 bytes) generated to the
gitignored `.data/a-full` and kept in page cache. Outputs go to gitignored `.out/`.

```sh
python3 official/generators/a_ingest.py --seed 1 --scale full --out .data/a-full
```

## Tools

- `bench.py`: builds each `--variant NAME=PATH.rs` (first one is the baseline) with
  `rustc --edition 2021 -C opt-level=3 -C codegen-units=1 -C lto=fat -C panic=abort -C target-cpu=x86-64-v3`
  into the gitignored `target/`, records source and binary SHA-256, then per thread count runs
  `--warmup` discarded rounds and `--runs` measured rounds. Each round runs every variant once in
  a freshly shuffled order from a seeded RNG (seed stored in the report). Before each run the old
  `summary.txt` is removed; wall time is `time.perf_counter` around the child, utime, stime and
  maxrss come from `os.wait4`, and every output SHA-256 must equal the published full seed-1 hash
  `495ca096...1cd3`. The JSON report has every sample plus median, min, mean of the middle 60%,
  a board-style statistic (mean of the middle 3 of each consecutive block of 5 runs, averaged),
  and per-round paired ratios candidate/baseline with their median and win fraction.
- `check.py BINARY`: full correctness suite. Full seed-1 hash at `SD_THREADS` 1, 2, 3, 6, 8, 12
  and unset, `track-a-verification/test.py --io directories`, `page_end_test.py` against the
  official reference, `latency_grid_test.py`, and sample seeds 2, 98, 999, 4242 byte-compared
  with the official reference output (generated under `.data/` if missing). Exits non-zero on
  any failure.
- `baseline.rs`: exact copy of `track-a/src/main.rs` at the branch point (`speed-demon`).
- `parse-time.py`: parse-phase-only interleaved timing of patched source copies (see Parse breakdown).
- `adversarial.py --binary BIN [--quick]`: endpoint lengths 1 to 300, equal-cheap-word families,
  5,000 and 70,000 distinct endpoints, boundary latencies, and (added with the summary work) groups
  of every size 1 to 200 with tied, equal, near-2^31 and near-2^32 or 32-bit-wide latencies,
  byte-compared with the official reference.
- `bench.py` variants may carry extra rustc arguments after a second `=`, for example
  `--variant "static=track-a/src/main.rs=-C target-feature=+crt-static"`.
- `pairs.py REPORT.json CAND:BASE ...`: paired ratio medians between any two variants of one
  `bench.py` report (for stepwise effects inside one multi-variant run).
- `startup.py`: empty-input wall time (startup and exit) of variants against `/bin/true`.
- `micro-ranks.rs`: single-thread microbenchmark of the small-group percentile paths.

```sh
python3 experiments/a-x86-speed/check.py track-a/target/release/solution
python3 experiments/a-x86-speed/bench.py --variant base=experiments/a-x86-speed/baseline.rs \
  --variant cand=experiments/a-x86-speed/<candidate>.rs --threads 8,12 --runs 41 --report <out>.json
```

The production build at the branch point passed `check.py` (all 14 checks).

## A/A noise

`baseline.rs` against itself under two names, 3 warmup rounds and 41 measured rounds per thread
count, in two independent invocations (shuffle seeds 1 and 2). All 352 outputs hashed correctly.

| Report | Threads | base median (s) | base2 median (s) | paired ratio median | base2 win fraction |
|---|---:|---:|---:|---:|---:|
| `aa-noise.json` | 8 | 0.0378 | 0.0381 | 1.0114 | 44% |
| `aa-noise.json` | 12 | 0.0465 | 0.0459 | 0.9874 | 66% |
| `aa-noise-2.json` | 8 | 0.0376 | 0.0374 | 1.0015 | 49% |
| `aa-noise-2.json` | 12 | 0.0465 | 0.0463 | 1.0061 | 44% |

Single-round paired ratios are wide (in `aa-noise.json` the 10th to 90th percentile is about
0.90 to 1.08 at 8 threads and 0.93 to 1.05 at 12), but the paired median over 41 rounds stayed
within 0.987 to 1.011. The A/A noise band for the paired median is therefore taken as
plus or minus 1.5%.

12 threads oversubscribes this 8 vCPU host (about 23% slower than 8), so it only approximates the
scoring box thread count; it is used as a regression guard rather than a target.

## Decision rule for later changes

Keep a change only if all of the following hold, measured against the immediately prior source:

1. `check.py` passes for a binary built from the candidate.
2. At 8 threads the paired median ratio candidate/baseline is below 0.985 (better than the
   A/A band) with at least 41 measured rounds.
3. At 12 threads the paired median ratio is at most 1.015 (no regression beyond noise).
4. Both conditions reproduce in a second independent `bench.py` invocation with a different
   shuffle seed.

Rejected candidates are archived under their own `experiments/a-<name>/` directory with the
variant source, baseline, JSON report and a README.

## Parse candidates

All numbers below are local x86 VM measurements (paired median ratio candidate/baseline over the
measured rounds, with the candidate's win fraction in brackets), not official scores. Every bench
output matched the full seed-1 hash. "Kept" sources passed `check.py` and `adversarial.py`.

### Parse breakdown

`parse-time.py` times only the parse phase (spawn to join of the parse threads, 8 threads, 31
interleaved rounds after 2 warmups) of patched copies of each source; `breakdown.rs` is
`baseline.rs` with `--cfg mode="..."` switches that skip work (diagnostic only, outputs not
correct in those modes). Report: `parse-breakdown.json`.

| Variant | What it does | Parse wall median |
|---|---|---:|
| `full` | `baseline.rs` | 26.66 ms |
| `lines` | only hops from newline to newline | 10.56 ms |
| `scan` | hour, endpoint scan and hash, latency; no table, no record push | 14.97 ms |
| `notable` | `scan` plus record push; no endpoint table | 18.39 ms |
| `nopush` | everything except the record push | 22.93 ms |
| `nocmp` | table probe without the byte compare (hash and length only) | 21.93 ms |
| `big` | local table pre-sized to 32,768 slots | 27.47 ms |
| `p1c`, `p3`, `p2`, `p2b` | the candidates below | 25.56, 24.80, 21.75, 22.08 ms |

The endpoint table costs about 8 ms of the 26.7 ms parse (about 4 ms of it the byte compare
against the endpoint's first occurrence in the mapped file, which the streaming reads keep
evicting from cache), the record push about 3.5 ms, field scanning about 4.5 ms. A larger table
is slower (more cache misses), so the fix is a smaller, denser footprint, not fewer collisions.

### Results

| Candidate | Description | 8 threads | 12 threads | Verdict | JSON |
|---|---|---:|---:|---|---|
| `p1-dense-ids.rs` | one shared `Mutex<HashMap>` handing out dense ids, shared id stored in the local table entry | 1.1104 (2%) | 1.1479 (2%) | rejected: lock contention while all threads discover the 1,842 endpoints at once | `p1-dense-ids.json` |
| `p1b-atomic-ids.rs` | 16 shards kept, dense ids from one `AtomicU32` (no id escapes), `ids` vector kept | 1.0067 (49%) | 1.0079 (49%) | rejected: within noise; id escapes are not a cost | `p1b-atomic-ids.json` |
| `p1c-table-ids.rs` | `p1b` plus the shared id stored in the local table entry (no `ids[local]` load) | 0.9747 (59%), 0.9875 (56%) | 0.9729 (71%), 0.9917 (62%) | not kept alone: second run missed 0.985; folded into `p2b` | `p1c-table-ids.json`, `p1c-table-ids-2.json` |
| `p3-avx2-endpoint.rs` | `p1c` plus a 64-byte AVX2 space scan, a fixed three-word endpoint hash (first, middle, last word and length) and an AVX2 masked compare for names under 64 bytes | 0.9876 (61%) | 1.0117 (29%) | not kept alone (vs `p1c` in the same run: 0.9906 / 0.9956); folded into `p2b` | `p3-avx2-endpoint.json` |
| `p2-arena.rs` | `p3` plus names copied into one compact per-thread arena (compare no longer touches the mapped file) | 0.8717 (98%) | 0.8537 (100%) | superseded by `p2b` (same run: 0.8681 / 0.8538) | `p2-arena.json` |
| `p2b-inline.rs` | `p2` with hash, length and shared id stored inline in the arena entry before the name, so a probe is slot then one arena entry | 0.8514 (97%), 0.8536 (98%) | 0.8414 (95%), 0.8409 (98%) | **kept** (production) | `p2b-inline.json`, `p2b-inline-2.json` |

`p2b` correctness: `check.py` (14 checks), `adversarial.py` (every endpoint length 1 to 300 under
all methods, equal-cheap-word families, 5,000 and 70,000 distinct endpoints with ids past 2047,
boundary latencies, at 1, 2, 3, 7 and 12 threads) on the AVX2 build, on a build with a forced
constant hash (every probe collides; `--quick`), and on a scalar build without
`target-cpu=x86-64-v3` (fallback `eq_mask`; also full seed-1 hash).

The rows below are measured against `cur-1.rs`, the production source after `p2b` (identical to
`p2b-inline.rs`). Parse-phase medians at 8 threads from `parse-p4.json`: `cur` 21.71 ms, `p4a`
20.98, `p4b` 21.23, `p5` 21.12.

| Candidate | Description | 8 threads | 12 threads | Verdict | JSON |
|---|---|---:|---:|---|---|
| `p4a-hour-swar.rs` | hour from one 8-byte load of `MM-DDTHH` with nibble arithmetic instead of five byte loads | 0.9776 (70%), 0.9949 (57%) | 0.9756 (75%), 0.9759 (70%) | not kept alone: 8-thread effect did not reproduce; folded into `p4ab` | `p4a-p5.json`, `p4a-hour-swar-2.json` |
| `p4b-long-endpoints.rs` | second 64-byte AVX2 scan and masked compare for endpoints of 64 to 127 bytes (about 4% of lines are 82 bytes) instead of a word loop and `memcmp` | parse phase only: 21.23 vs 21.71 ms | | folded into `p4ab` | `parse-p4.json` |
| `p4ab-trim.rs` | `p4a` plus `p4b` | 0.9784 (65%), 0.9842 (58%) | 0.9861 (64%), 0.9904 (60%) | **kept** (production) | `p4ab-trim.json`, `p4ab-trim-2.json` |
| `p5-dynamic.rs` | 8 line-aligned ranges per thread taken from an atomic counter, one table and hour buckets per thread | 1.0011 (48%) | 1.0087 (44%) | rejected on this homogeneous VM; worth an official test only if the scoring box's 12 threads mix P and E cores | `p4a-p5.json` |

`p4ab` correctness: `check.py`, `adversarial.py` on the AVX2 build (cargo), forced-collision
build (`--quick`) and scalar build, and the scalar full seed-1 hash.

The rows below are measured against `cur-2.rs`, the production source after `p4ab` (identical to
`p4ab-trim.rs`). Parse-phase medians at 8 threads: `parse-p6.json` `cur` 21.15 ms, `p6` 21.60,
`p6b` 20.27; `parse-p7.json` `cur` 20.79, `p6b` 20.14, `p7` 20.12.

| Candidate | Description | 8 threads | 12 threads | Verdict | JSON |
|---|---|---:|---:|---|---|
| `p6-push-trim.rs` | table growth check moved to the insert path, one `len == capacity` check before the push, branch-free escape test | parse phase only: 21.60 vs 21.15 ms | | rejected (slower parse phase) | `parse-p6.json` |
| `p6b-two-word-hash.rs` | endpoint hash from the first and last words and length only, one multiply | 0.9854 (60%), 0.9670 (73%), 0.9861 (62%) | 0.9915 (62%), 0.9779 (65%), 0.9804 (68%) | rejected under the rule: every ratio is below 1, but two of three invocations missed 0.985 by under 0.002; a candidate for stacking with another small win | `p6b-two-word-hash.json`, `-2`, `-3` |
| `p7-cold-insert.rs` | `p6b` plus the table insert path moved to a `#[cold]` non-inlined function | parse phase only: 20.12 vs 20.14 ms for `p6b` | | rejected (no effect over `p6b`) | `parse-p7.json` |

### Cumulative

`parse-cumulative.json` (41 rounds, seed 71): production after FEAT-002 against `baseline.rs`,
paired median 0.8494 at 8 threads (93% of rounds won) and 0.8303 at 12 (100%); medians 0.0375 s
to 0.0320 s at 8 threads and 0.0464 s to 0.0387 s at 12. Local x86 VM only.

## Summary, scheduling, output and build candidates

All numbers are local x86 VM measurements, not official scores. Every bench output matched the
full seed-1 hash. Ratios are paired medians candidate/baseline (win fraction in brackets).

### Where the summary time went

Ad hoc instrumented copies of `s1-kernel.rs` (not archived; timers around each stage, summed
over the 8 summary workers) showed about 5 ms for the count pass,
13 to 15 ms for the scatter pass, 25 ms for the three-percentile selection and 11 ms for
formatting, out of about 55 to 60 ms of summary CPU at 8 threads (3.6, 6.7, 17.2 and 6.2 ms at
4 threads, where no two workers share a core). Group sizes are heavy-tailed (median 5 records per
(hour, endpoint) group), so most of the selection cost is per-group overhead on small groups:
`micro-ranks.rs` measured 33, 66, 140 and 237 ns per group for random groups of up to 8, 16, 32
and 64 values with the previous sort/select path, against 14, 19, 29 and 69 ns with AVX2 rank
counting (identical answers). A scalar rank-counting version (no intrinsics) was slower than
the sort in the same microbenchmark and was dropped without a wall-time run.

### Results

`cur-2.rs` is the production source after FEAT-002. Stepwise rows come from two six-variant
invocations (`summary-chain.json`, seed 401, and `summary-chain-2.json`, seed 402; 41 rounds at
8 and 12 threads each), read with `pairs.py` against the previous step.

| Candidate | Description | 8 threads | 12 threads | Verdict | JSON |
|---|---|---:|---:|---|---|
| `s1-kernel.rs` | summary groups laid out in rank order but indexed by id (no `rank[id]` lookups), count and errors packed in one `u64` per id, per-worker `counts`/`next`/`lat` reused across hours, numbers formatted with a two-digit table into one line buffer | 0.9876 (66%), 0.9948 (59%) | 0.9777 (66%), 0.9968 (54%) | not kept alone; folded into `s2c` (it is the base of the later steps) | `summary-chain.json`, `-2` |
| `s1e-small-ranks.rs` | `s1` plus AVX2 rank counting for groups of up to 64 values: for every value count the values below it (branch-free, 8 lanes per compare), the value of rank r is the largest value with at most r values below it; larger groups keep `select_nth_unstable`; non-AVX2 builds keep the old path | 0.9775 (63%), 0.9575 (80%) | 0.9802 (68%), 0.9644 (78%) | folded into `s2c` | `summary-chain.json`, `-2` |
| `s2b-reuse-threads.rs` | `s1e` with the parse threads going on to summarize: a `Barrier` after parsing, one thread sorts the names and builds the hour jobs, a second barrier, then all take hours (no second thread set) | 0.9954 (51%), 0.9675 (73%) | 1.0008 (49%), 0.9839 (68%) | folded into `s2c`; leave-one-out below | `summary-chain.json`, `-2` |
| `s2c-two-word-hash.rs` | `s2b` plus the FEAT-002 near-miss `p6b` (endpoint hash from first and last words and length, one multiply), names moved out of the shared maps instead of borrowed | 0.9319 (78%), 0.9341 (95%) vs `cur-2.rs` | 0.9420 (90%), 0.9259 (95%) vs `cur-2.rs` | **kept** (production) | `s2c-keep-404.json`, `s2c-keep-405.json` |
| leave-one-out | `s1f-two-word-hash.rs` (`s2c` without thread reuse) against `s2c` | 1.0242 (27%) | 1.0061 (46%) | thread reuse stays | `leave-one-out.json` |
| `s3a-direct-format.rs` | `s2b` plus lines written straight into a reused output buffer (fixed 21-byte prefix copy, names in one padded arena copied as one 128-byte block, written buffers returned by the main thread for reuse) | 1.0101 (46%), 1.0266 (29%) vs `s2b` | 0.9900 (63%), 1.0071 (46%) vs `s2b` | rejected | `summary-chain.json`, `-2` |
| `s3b-two-word-hash.rs` | `s3a` plus `p6b` (the same format change on top of `s2c`) | 0.9829 (51%), 1.0104 (41%) vs `s2c` | 1.0237 (39%), 0.9980 (51%) vs `s2c` | rejected (no reproducible gain, 12-thread regression in one run; `s3-format-vs-s2c.json` used `s2c` before a behaviour-neutral refactor) | `s3-format-vs-s2c.json`, `leave-one-out.json` |

Rejected screens, `summary-rejected.json` (seed 407, 21 rounds, against `s1-kernel.rs` unless noted):

| Candidate | Description | 8 threads | 12 threads | Verdict |
|---|---|---:|---:|---|
| `s1b-parse-counts.rs` | parse threads count records per (hour, id) below 2048, so the summary skips its count pass | 1.0112 (43%) | 1.0239 (29%) | rejected: the parse-side increment costs what the pass saved |
| `s1c-reuse-out.rs` | written output buffers returned to the workers for reuse | 0.9709 (71%) | 1.0017 (48%) | rejected: an earlier 21-round screen gave 1.0003 at 8 threads (not saved), so the 8-thread effect did not reproduce |
| `s1-sort64.rs` | full sort for groups of up to 64 values instead of 16 | 1.0084 (43%) | 1.0231 (33%) | rejected |
| `s1-forget.rs` | records leaked after summarizing instead of freed (checks munmap cost) | 1.0057 (43%) | 1.0020 (38%) | rejected: freeing is not a cost |
| `s2a-largest-first.rs` | hours dispatched largest first (against `s1e`) | 1.0947 (10%) | 1.0375 (19%) | rejected: hour 0 arrives late, so the writer holds most hours and writes them in a serial tail |

### B1: static linking

`-C target-feature=+crt-static` cannot be linked on this host: Amazon Linux 2023 has no
`libc.a` installed (glibc-static), and the sandbox cannot reach the package repositories
(`rust-lld: error: unable to find library -lc`). It was therefore not benchmarked and not
applied; `track-a/.cargo/config.toml` is unchanged. The Dockerfile build was not run locally
either (no working docker here). `startup.py` (`b1-startup.json`, 300 shuffled rounds, empty
input, 8 threads) gives the size of the prize: `/bin/true` 0.92 ms (Python spawn floor),
`cur-2.rs` 1.82 ms, `s2c` 1.63 ms (one thread set instead of two). The dynamic binary links only
`libc.so.6` and `libgcc_s.so.1`, so static linking could save at most a few tenths of a
millisecond of the remaining 0.7 ms; it needs a measurement on a host with glibc-static
(Debian's `libc6-dev` in the build image ships `libc.a`).

### Correctness of the kept source

`check.py` passed on the cargo build of production (`s2c`); `adversarial.py` (including the new
group-sizes case) passed at 1, 2, 3, 7 and 12 threads on the AVX2 cargo build, on a scalar build
without `target-cpu` (old selection path; also full seed-1 hash) and with `--quick` on a build
with a forced constant endpoint hash. The full hash also matched at `SD_THREADS` 73 and 100 (more
threads than hours). A mutant that drops the sign bias in the AVX2 compare fails the group-sizes
case. `parse-time.py` now also handles the barrier layout (time until the first thread leaves the
parse barrier): `parse-final.json`, `cur-2.rs` 21.11 ms, production 19.71 ms at 8 threads.

### Cumulative

`final.json` (41 rounds, seed 501, every output hash verified): `baseline.rs` (the branch point)
against the final production `track-a/src/main.rs`, paired median 0.7848 at 8 threads (100% of
rounds won; medians 0.0379 s to 0.0296 s), 0.7790 at 12 threads (98%; 0.0468 s to 0.0365 s) and
0.7800 with the default thread count (98%; 0.0377 s to 0.0294 s). Local x86 VM only.
