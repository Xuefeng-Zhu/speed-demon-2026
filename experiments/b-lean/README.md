# Track B candidate: leaner source with equal speed (local sandbox measurements, not official scores)

`baseline.rs` is byte-identical to `track-b/src/main.rs` at `8de6f94` (b-filter-parse, `experiments/b-filter-parse/candidate.rs`), SHA-256 `3df3ebd80f06ea5a61060d48401300a259a79dde7040216072f8d9594b408895`. `candidate.rs` is byte-identical to the committed `track-b/src/main.rs` of this candidate, SHA-256 `8aefbf5adfb6800c28b32aa0ff7279bd8ee990689524f91c61a2c438e68e3017`. `Cargo.toml`, `Cargo.lock` and `Dockerfile` are unchanged.

The goal is a smaller S with no slowdown. The algorithm, data layout, prefetching and thresholds are unchanged; only how the code is written changes, plus two small rewrites of serial bookkeeping (phrase hits and the document count) that give the same values. Memory work is on hold and none was attempted.

All numbers below are local sandbox measurements, not official scores and not board results. No official board run exists yet for this source.

## S and expected K effect

S is `rustfmt --edition 2021 --emit stdout <file> | grep -cvE '^\s*$|^\s*//'` (non-blank, non-comment lines after rustfmt with default settings).

| Source | S | Raw lines |
| --- | ---: | ---: |
| `baseline.rs` | 634 | 652 |
| `candidate.rs` | **567** | 674 |

S drops by 67 lines (-10.6%). Raw lines grow by 22 because several lines that rustfmt used to break into 4 to 13 lines are now split by hand into 2 or 3 short statements; the committed file keeps the repo's style of not being rustfmt-formatted. With K proportional to S^-0.15, (567/634)^-0.15 = 1.0169, about +1.7% K from S alone, the same as a 3.4% wall-time gain at T^-0.5. Doc comments were kept and a few were added; they do not count in S.

## What changed

Most of the S drop comes from statements that rustfmt expanded heavily: long method chains (over `chain_width` 60), `if` expressions over 50 characters and long tuples. Each is rewritten so rustfmt keeps it short, with the same operations.

1. **Document count (13 -> 2 S lines).** `ndocs` was the id of the line found by `rposition` of the second-to-last LF and `line_start`. It is now `data.rsplit(|&b| b == b'\n').nth(1)` (the last line, since `docs.txt` ends with a LF) and `id_at(l, 0) + 1`, or 0 for an empty corpus. `line_start` of a line start returns it unchanged, so the call was redundant.
2. **Phrase hits (20 -> 10 S lines).** The hits were collected, stable-sorted by query, offset with a counting pass (`hoff`), and every phrase query copied its ids into a new `Vec` and deduplicated it. Now `hits` is extended from each chunk, `sort_unstable()` on (query, id) and `dedup()` once, and a phrase query takes its slice with two `partition_point` calls. The ids per query come out in the same ascending, deduplicated order. 19,427 hits on seed 1, so the sort is negligible.
3. **`sorted_line` helper.** The list ending of `boolean()` and the phrase answer both printed a sorted id list with its count and sum; both now call `sorted_line(out, ids)`.
4. **`boolean()` arms.** The bitmap-term arms `(false, b'A')` and `(false, b'N')` merge into `r.retain(|&d| get(row, d) == and)` (`and` is computed once at the top of the loop). A `clear` closure sits next to `get` and `set` for the AND NOT of a list into the bitmap.
5. **Tokenizer bookkeeping in `for_each_doc`.** The tuple assignment `(carry, starts, ends) = (...)` and the two `if` expressions for `s` and `open` became short statements (same branch-free selects), and the long-token lookup moved into a `long` closure. `Plan::slot` names its probe predicate `hit`. `masks()` names the movemask conversion `bits`; the portable fallback loop uses `enumerate()`.
6. **Anchor prefetch passes, same three levels.** The prefetch of `aoff`, the first anchor and the phrase copy for all anchors of a document still runs level by level; the passes are written as short loops over `anch = &anch[..m]` with a `term` closure, and the compare loop reuses the `ranges` closure.
7. **Plan building in `main`.** The filter loop also sets the no-term id of empty slots (one pass instead of two). The sample document frequency keeps its meaning (documents containing the term) but stores `(count, last document)` per term in one `Vec<(u32, u32)>` instead of two vectors. `common` is a `partition_point` on the already sorted `bools` instead of a filter count. `order` is built with `concat` plus `extend`. `Scratch` derives `Default`. `claim` gets a `take` closure.
8. **CSR count pass** is a `for` loop instead of a 4-line chain.

Steps of the work, each checked on the full seed-1 hash: `step-a.rs` (items 1 to 3, the merged `retain` arm, the tokenizer statements, `hit`, `bits`, and the filter, `common`, `order` and `Scratch` parts of item 7; S 590), `step-b.rs` (plus item 6 and the frequency pair; S 579), then the `long` and `clear` closures, the fallback `enumerate()`, `claim`, the renumbering loop and item 8 give 567.

**A memory slip found and fixed.** The first version of item 7 wrote `vec![(0, 0); n]` with `sdocs` compared as `usize`, which inferred `(u32, usize)` (16 bytes per term, about 1.2 MB touched in the sample scan instead of 0.6 MB). It showed as a +0.3 to +1.6% max RSS median in `v1-t8-report.json` and `v1-t6-report.json` (wall -0.85% and -1.57%). Typing it `(u32, u32)` fixed it: `h2h-freq32-report.json` gives RSS 64,808 vs 65,348 KiB against that first version, wall -0.53% (8/11). The final reports below are of the fixed source.

## Tried and rejected

Head to head screening runs, 1 warmup plus 11 pairs at 8 threads, against the step the variant was built from (`step-a.rs` for the prefetch variants, `step-b.rs` for the others). Each variant source is in this folder.

| Variant | S | Paired wall | Wins | Paired CPU | Max RSS cand / base KiB | Decision |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| `variant-nopf.rs`: no anchor prefetch passes | 577 (-13 vs step-a) | +2.15% | 2/11 | +1.71% | 64,876 / 64,780 | rejected, slower |
| `variant-pf1.rs`: prefetch `aoff` only | 580 (-10) | +3.10% | 3/11 | +4.00% | 64,800 / 64,884 | rejected, slower |
| `variant-seen.rs`: drop list-term repeats in the scan callback with a per-term last-document array, CSR without dedup and without gap closing | 569 (-10 vs step-b) | +2.83% | 2/11 | +4.14% | 67,244 / 65,448 | rejected, slower and +1.8 MB RSS (the array costs a load and store per token) |
| `variant-nokeypf.rs`: no slot prefetch in `for_each_doc` | 578 (-1) | +0.15% | 5/11 | -0.61% | 65,412 / 65,348 | rejected: neutral here, but 1 S line does not justify dropping the latency hint for the 35% lookup part on a different memory system |
| `variant-tokfreq.rs`: token frequency instead of document frequency in the sample | 576 (-3) | -0.23% | 7/11 | +0.18% | 65,000 / 65,364 | rejected: neutral, but it changes the plan (seed 1: 355 instead of 347 bitmap terms; sample-2: 314 vs 307) for 3 lines, so the documented, measured rule stays |

Not attempted: a cheaper anchor rule than "rarest term in the sample". The sample scan is still needed for the bitmap choice, so a different anchor rule would save no S and could only change the 4% phrase share. The three bitmap-into-bitmap arms in `boolean()` stay separate so each loop keeps a single vectorizable operation.

## Environment

| Item | Value |
| --- | --- |
| CPU | Intel Xeon Platinum 8488C, 8 vCPUs (4 cores x 2 SMT), shared host |
| Compiler | rustc 1.92.0 (official Dockerfile pins a different Rust) |
| Flags | `RUSTFLAGS='-Ctarget-cpu=x86-64-v3' cargo build --release` with the repo profile (fat LTO, 1 codegen unit, panic=abort) |
| PGO | none locally (the official build uses PGO) |
| Data | full seed 1 (`docs.txt` 253,827,587 B, `queries.txt` 1,763,534 B) |
| Harness | `experiments/b-linux-profile/run.py`, candidate and baseline interleaved, hash asserted on every run; `experiments/b-filter-parse/pair.py` for paired medians |

The scoring box (i5-13500, 6 P-cores / 12 threads) differs from this host, so the deltas are indicative only. On this host |delta| below about 1% is noise.

## Paired results vs the b-filter-parse binary

Baseline binary: `baseline.rs` built as above, SHA-256 `defee9c5f546b8d62dae50ed44973dca27f8b9054f92437fdc2ad75f16c000d5`. Candidate binary SHA-256 `82089c414ff098d27d2917d65cbc5ba760f55a428baa084b94ec0109cd159279`. 1 warmup plus 21 measured runs per binary, alternating. Medians in ms.

| Report | Threads | Cand wall | Base wall | Paired wall | Wins | Paired CPU | Max RSS cand / base KiB |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `lean-final-t8-report.json` | 8 | 210.5 | 213.3 | **-2.01%** | 16/21 | -1.55% | 64,828 / 64,884 |
| `lean-final-t6-report.json` | 6 | 254.8 | 259.8 | **-1.61%** | 18/21 | -2.04% | 63,780 / 64,384 |

Earlier screening of the same direction: `screen-a-t8-report.json` (`step-a.rs` vs baseline, 7 pairs) -0.44% (4/7); `h2h-b-vs-a-report.json` (`step-b.rs` vs `step-a.rs`, 11 pairs) -0.53% (6/11). None of the changes is expected to make the scan faster, so read the final result as "no slowdown, possibly a small gain from the phrase answer no longer allocating per query"; a -2% gain is near the noise level of this host. Max RSS is equal within noise.

## Correctness

- Full seed 1: every measured and warmup run in every report above produced `f86973c210228141bcb6f1f1b10188ad2a9b65f71e7cd7cf4590b38de4e80927`, asserted by `run.py`; every variant and step was also checked against this hash when built.
- `experiments/b-filter-parse/check_all.sh` (20 tiny seeds, sample seeds 2, 3, 4, 5, 7 and 11 edge fixtures, compared byte for byte with `official/reference/b_index.py`): pass=34 fail=0 xfail=2 at the default thread count, at 1 and at 12 threads. The two xfails, `edge/no_lf` and `edge/no_lf_docs` (`docs.txt` without a trailing LF, outside spec 2.1), panic in `masks()` as on the baseline. `variant-seen.rs` and `step-b.rs` also passed check_all before timing.
- The x86-64-v3 build and the portable build (`RUSTFLAGS='-Ctarget-cpu=x86-64' cargo build --release --target-dir ...`) compile without warnings; the portable binary contains no ymm instructions and also passes check_all (pass=34).

## Files

| File | Content |
| --- | --- |
| `baseline.rs`, `candidate.rs` | sources (SHA-256 above) |
| `step-a.rs`, `step-b.rs` | intermediate steps used as screening baselines |
| `variant-*.rs` | rejected variants from the table above |
| `lean-final-t8-report.json`, `lean-final-t6-report.json` | final 21-pair reports vs the baseline binary |
| `v1-t8-report.json`, `v1-t6-report.json` | 21-pair reports of the first version with the `(u32, usize)` slip |
| `h2h-*-report.json`, `screen-a-t8-report.json` | screening reports listed above |

## Reproduce

```sh
D=/projects/sandbox/.data; E=experiments/b-lean
build() { cp $1 track-b/src/main.rs && touch track-b/src/main.rs &&
  (cd track-b && RUSTFLAGS='-Ctarget-cpu=x86-64-v3' cargo build --release) && cp track-b/target/release/solution $D/bin/$2; }
build $E/baseline.rs cand-final
build $E/candidate.rs lean-final
for t in "" 1 12; do experiments/b-filter-parse/check_all.sh $D/bin/lean-final $t 2>/dev/null; done
for t in 8 6; do
  python3 experiments/b-linux-profile/run.py --binary $D/bin/lean-final --baseline $D/bin/cand-final \
    --data $D/speed-b-full --runs 21 --threads $t --report $D/lean-final-t$t-report.json
done
python3 experiments/b-filter-parse/pair.py $D/lean-final-t*-report.json
for f in $E/baseline.rs $E/candidate.rs; do rustfmt --edition 2021 --emit stdout $f | grep -cvE '^\s*$|^\s*//'; done
```
