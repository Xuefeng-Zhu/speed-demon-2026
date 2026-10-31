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
