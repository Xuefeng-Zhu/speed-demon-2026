# Track B candidate: query-term filter before slot probe and presized intern table (local sandbox measurements, not official scores)

`baseline.rs` is byte-identical to `track-b/src/main.rs` at `dddc0ea` (and to `experiments/b-linux-profile/baseline.rs`), SHA-256 `6607a94ce52f9d1fd25e99f2e5705a9f79bc1f47b2c398bda148594124e63709`. `candidate.rs` is byte-identical to the committed `track-b/src/main.rs` of this candidate, SHA-256 `3df3ebd80f06ea5a61060d48401300a259a79dde7040216072f8d9594b408895`. `Cargo.toml`, `Cargo.lock` and `Dockerfile` are unchanged.

It implements items 2 and 3 of the ranked bottlenecks in `experiments/b-linux-profile/README.md`: slot lookup is 34.9% of the index scan and 20.8% of tokens are not query terms (item 2), and query parse/intern is about 15.35 ms of serial time (item 3).

All numbers below are local sandbox measurements, not official scores and not board results. No official board run exists yet for this source.

## What changed

1. **Query-term filter (item 2).** The existing 24-bit home hash is factored out as `Plan::hash(k)` (`home()` is now `hash & (len - 1)`). After query interning, `main` builds `plan.filter`, a 1<<20-bit (128 KiB) `Vec<u64>` with bit `hash(k) % FILTER` set for every occupied key, and records `plan.empty`, the index of a known empty slot. In `for_each_doc`, a short token (at most 16 bytes) whose filter bit is clear is replaced by the empty key `[0; 2]` at `plan.empty`. It still goes through the normal prefetch and lookup, but the empty-key match at an empty slot is immediate and predictable instead of a probe run of up to 2/3 load. A false positive (bit set by another key) simply takes the normal probe with the real key, and a query term can never have a clear bit, so correctness never depends on the filter. The long (more than 16 byte) path is unchanged.
2. **Presized intern table (item 3).** `plan.grow(1 << 12)` became `plan.grow((qtext.len() / 16 | 64).next_power_of_two())`. On full seed 1 this gives 131,072 slots up front, the same final size the baseline reaches after several rehashes (75,747 terms, load 0.58); the table still grows if needed. The `| 64` is required: without it a tiny query file gives a 2-slot table, and `edge/no_lf` hung forever probing a full table in an earlier draft.

Diff: 26 lines added, 5 removed. S (`rustfmt --edition 2021 --emit stdout <file> | grep -cvE '^\s*$|^\s*//'`) 620 -> 634 (+14, +2.26%; at the 0.3x rule the break-even wall gain is about 0.68%). Raw lines 631 -> 652 (+21). All 14 S lines are the filter; the presize is 0 S lines.

## Tried and dropped

| Variant | Result | Why dropped |
| --- | --- | --- |
| Parallel query parse into per-thread offsets, then serial intern | parse/intern 15.0 to 18.3 ms (worse than baseline 14.8 to 16.0 ms); t8 paired wall -0.59% alone, -3.32% with the filter | Slower than the presize alone and about +30 S lines more than this candidate. `par()` parse was only 1.4x faster than serial (allocation and page-fault bound), plus 1.1 ms collecting term slots. |
| Prefetching 16 terms ahead during intern | no gain (no-prefetch variant same or faster) | Extra lines, no measured benefit |
| Compact array form `h = [plan.empty, plan.home(k)][bit]` keeping the real key | 1 S line smaller, but 0.9% to 1.9% slower head to head | The kept form (zero key at empty slot) is faster |
| Filter sizes 1<<18, 1<<19, 1<<21 bits (kept form) | each gave a smaller paired gain than 1<<20 in 8-thread runs | Size choice |
| Miss mapped to `h = !0` with a branch | slower than baseline at 1<<18, 1<<20 and 1<<22 bits | Branch cost |

## Environment

| Item | Value |
| --- | --- |
| CPU | Intel Xeon Platinum 8488C, 8 vCPUs (4 cores x 2 SMT), shared host |
| Compiler | rustc 1.92.0 (official Dockerfile pins a different Rust) |
| Flags | `RUSTFLAGS='-Ctarget-cpu=x86-64-v3' cargo build --release` with the repo profile (fat LTO, 1 codegen unit, panic=abort) |
| PGO | none locally (the official build uses PGO) |
| Data | full seed 1 (`docs.txt` 253,827,587 B, `queries.txt` 1,763,534 B) |
| Harness | `experiments/b-linux-profile/run.py`, baseline and candidate interleaved, hash asserted on every run |

The scoring box (i5-13500, 6 P-cores / 12 threads) differs from this host, so the deltas below are indicative only.

## Paired results vs dddc0ea baseline

Each report: 1 warmup plus 21 measured runs per binary, candidate and baseline alternating. Deltas are medians of per-pair ratios from `pair.py`; "wins" counts pairs where the candidate was faster. Medians in ms.

| Report | Threads | Cand wall | Base wall | Paired wall | Wins | Paired CPU | Max RSS cand / base KiB |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `cand-final-t8-report.json` (this candidate) | 8 | 214.1 | 224.2 | **-4.59%** | 19/21 | -3.96% | 64,780 / 65,684 |
| `cand-final-t6-report.json` (this candidate) | 6 | 280.1 | 289.4 | **-3.51%** | 21/21 | -4.17% | 64,536 / 64,336 |
| `cand-final-t12-report.json` (this candidate, 12 threads on 8 vCPUs, oversubscribed) | 12 | 240.9 | 251.3 | **-2.83%** | 16/21 | -2.35% | 69,616 / 71,976 |
| `cand-filter-alone-t8-r2-report.json` (filter, baseline `grow(1 << 12)`) | 8 | 220.2 | 228.3 | -2.95% | 20/21 | -3.88% | 65,980 / 65,900 |
| `cand-filterE-final-t8-report.json` (filter alone, earlier run) | 8 | 221.3 | 227.9 | -2.99% | 19/21 | -4.17% | 65,928 / 65,888 |
| `cand-presize-t8-report.json` (presize alone) | 8 | 225.2 | 225.9 | -1.38% | 14/21 | -0.25% | 64,716 / 65,784 |
| `cand-presize-t8-r2-report.json` (presize alone, repeat) | 8 | 221.2 | 221.8 | +0.20% | 10/21 | +0.22% | 64,616 / 65,832 |
| `cand-parse-final-t8-report.json` (parallel parse alone, dropped) | 8 | 225.6 | 225.1 | -0.59% | 12/21 | +0.83% | 65,868 / 65,848 |
| `cand-both-t8-report.json` (filter + parallel parse, dropped) | 8 | 220.2 | 225.1 | -3.32% | 17/21 | -3.17% | 66,272 / 65,680 |

Head to head (no dddc0ea baseline; "base" is the other variant):

| Report | Candidate vs base | Paired wall | Wins |
| --- | --- | ---: | ---: |
| `h2h-filter-vs-filterE-report.json` | compact array filter vs kept zero-key filter | +0.93% | 8/21 |
| `h2h-final-vs-arr-report.json` | this candidate vs compact array candidate | -1.88% | 15/21 |

An earlier run of identical candidate code at 8 threads gave -5.05% (20/21); its report was superseded and is not included. The presize alone is within noise on wall, but it removes about 2 ms of serial time (below) for 0 S lines, and serial time weighs more on the 12-thread scoring box, so it is kept. Max RSS is within about 1.5% of the baseline at 6 and 8 threads and 3% lower at 12 threads. The filter-size and `h = !0` reports are earlier screening runs kept outside the repo and not copied here.

## Serial parse/intern time

Measured with temporary `Instant` timing on the main thread from after reading `queries.txt` to before `map_file`, 8 threads (instrumentation removed before commit):

| Version | parse/intern ms |
| --- | ---: |
| baseline `dddc0ea` | 14.8 to 16.0 |
| presized table (this candidate) | 12.6 to 14.0 |
| parallel parse + presize + prefetch-16 intern (dropped) | 15.0 to 18.3 |

## Correctness

- Full seed 1: every measured and warmup run in every report above produced `f86973c210228141bcb6f1f1b10188ad2a9b65f71e7cd7cf4590b38de4e80927`, asserted by `run.py`.
- `check_all.sh` compares `results.txt` byte for byte with `official/reference/b_index.py` output on generated seeds tiny-1 to tiny-20 and sample-2, 3, 4, 5, 7, plus 11 handcrafted edge fixtures from `make_edge.py` (repeated terms, operator words as tokens, non-ASCII separators, absent and duplicate queries, 1/7/8/9/15/16/17/24/31/32-byte tokens and 16-byte prefix collisions, uppercase, missing final LF, one-kind terms, and `many_terms` with about 8,000 queries over about 30,000 words). Result: pass=34 fail=0 xfail=2 at default, 1 and 12 threads. The two xfails, `edge/no_lf` and `edge/no_lf_docs` (`docs.txt` without a trailing LF, outside spec 2.1), panic in `masks()` on the baseline too; this candidate does not change that.
- Filter false positives occur on every seed-1 run (about 7% filter occupancy) and are exercised by `many_terms` and `lengths`.
- Portable build `RUSTFLAGS='-Ctarget-cpu=x86-64' cargo build --release` compiles without warnings, contains no ymm instructions and passes `check_all.sh`. Note that `RUSTFLAGS=''` does not override `.cargo/config.toml`; pass an explicit `-Ctarget-cpu=x86-64`.
- The x86-64-v3 release build has no warnings.

## Files

| File | Content |
| --- | --- |
| `baseline.rs`, `candidate.rs` | sources (SHA-256 above) |
| `cand-*.json`, `h2h-*.json` | `run.py` reports listed above |
| `pair.py` | paired medians from reports: `python3 pair.py *.json` |
| `check_all.sh` | correctness checker; `CHK_ROOT` (default `/projects/sandbox/.data`) must contain `seeds/*/` and `edge/*/` with `docs.txt`, `queries.txt`, `ref/results.txt`; `CHK_TIMEOUT` (default 60 s) wraps each run |
| `make_edge.py` | builds the edge fixtures into `EDGE_ROOT` (default `/projects/sandbox/.data/edge`) using `official/reference/b_index.py` |

The copied `check_all.sh` adds the `CHK_ROOT` and `CHK_TIMEOUT` variables; the runs above used the equivalent original with a `timeout 60` wrapper binary.

## Reproduce

```sh
D=/projects/sandbox/.data; E=experiments/b-filter-parse
# data (outside the repo)
python3 official/generators/b_index.py --seed 1 --scale full --out $D/speed-b-full
for s in $(seq 1 20); do python3 official/generators/b_index.py --seed $s --scale tiny --out $D/seeds/tiny-$s; done
for s in 2 3 4 5 7; do python3 official/generators/b_index.py --seed $s --scale sample --out $D/seeds/sample-$s; done
for d in $D/seeds/*/; do python3 official/reference/b_index.py --data $d --out $d/ref; done
python3 $E/make_edge.py

# builds (cargo, as for the official target; touch to avoid a stale target)
mkdir -p $D/bin
cp $E/baseline.rs track-b/src/main.rs && touch track-b/src/main.rs
(cd track-b && RUSTFLAGS='-Ctarget-cpu=x86-64-v3' cargo build --release) && cp track-b/target/release/solution $D/bin/base-dddc0ea
cp $E/candidate.rs track-b/src/main.rs && touch track-b/src/main.rs
(cd track-b && RUSTFLAGS='-Ctarget-cpu=x86-64-v3' cargo build --release) && cp track-b/target/release/solution $D/bin/cand-final

# correctness
$E/check_all.sh $D/bin/cand-final 2>/dev/null
$E/check_all.sh $D/bin/cand-final 1 2>/dev/null
$E/check_all.sh $D/bin/cand-final 12 2>/dev/null

# paired timing (hash asserted), then summarize
for t in 6 8 12; do
  python3 experiments/b-linux-profile/run.py --binary $D/bin/cand-final --baseline $D/bin/base-dddc0ea \
    --data $D/speed-b-full --runs 21 --threads $t --report $D/cand-final-t$t-report.json
done
python3 $E/pair.py $D/cand-final-t*-report.json
```
