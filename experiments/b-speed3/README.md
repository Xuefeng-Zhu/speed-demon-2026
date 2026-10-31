# Track B candidate: branch-free scan writes, cheaper token key, tokenized flat query parse (local sandbox measurements, not official scores)

`baseline.rs` is byte-identical to `track-b/src/main.rs` at `a6a2151` (b-lean, `experiments/b-lean/candidate.rs`), SHA-256 `8aefbf5adfb6800c28b32aa0ff7279bd8ee990689524f91c61a2c438e68e3017`. `candidate.rs` is byte-identical to the committed `track-b/src/main.rs` of this candidate, SHA-256 `d39202542d59ccededa7fd0b7bbbd3c703d63f5dd98a80e02dd97f2acaff66b9`. `Cargo.toml`, `Cargo.lock` and `Dockerfile` are unchanged. std only, no new dependencies.

All numbers below are local sandbox measurements, not official scores and not board results. No official board run exists yet for this source.

## Summary

| | baseline (b-lean) | candidate |
| --- | ---: | ---: |
| S (`rustfmt --edition 2021 --emit stdout <file> \| grep -cvE '^\s*$\|^\s*//'`) | 567 | **558** (-9, -1.6%) |
| Raw lines | 674 | 672 |
| 8 threads, 21 pairs: median wall | 208.1 ms | 179.0 ms, paired **-14.16%** (21/21 wins) |
| 6 threads, 21 pairs: median wall | 256.3 ms | 201.7 ms, paired **-21.82%** (21/21) |
| 12 threads (oversubscribed on 8 vCPUs), 21 pairs | 223.9 ms | 192.3 ms, paired **-13.91%** (21/21) |
| Max RSS median (8 / 6 / 12 threads) | 64,796 / 63,116 / 68,960 KiB | 62,632 / 62,064 / 67,244 KiB |

S goes down overall. Per step, the only S increases were +1 line (step 2) and +6 lines (step 4, removed again in step 5); see the table under "Kept changes".

## Environment

| Item | Value |
| --- | --- |
| CPU | Intel Xeon Platinum 8488C, 8 vCPUs (4 cores x 2 SMT), shared host |
| Compiler | rustc 1.92.0 (official Dockerfile pins a different Rust) |
| Flags | `RUSTFLAGS='-Ctarget-cpu=x86-64-v3' cargo build --release` with the repo profile (fat LTO, 1 codegen unit, panic=abort) |
| PGO | none locally (the official build uses PGO) |
| Data | full seed 1 (`docs.txt` 253,827,587 B, `queries.txt` 1,763,534 B) |
| Harness | `experiments/b-linux-profile/run.py` (candidate and baseline interleaved, hash asserted on every run), `experiments/b-filter-parse/pair.py` for paired medians |
| Baseline binary | `/projects/sandbox/.data/bin/lean-final`, SHA-256 `82089c414ff098d27d2917d65cbc5ba760f55a428baa084b94ec0109cd159279` (the b-lean build, verified before use) |
| Candidate binary | SHA-256 `aef038ddf1abe36cac61eaa33780df4cdc8efd03c784f52ead276b77e36ac0eb` |

The scoring box (i5-13500, 6 P-cores / 12 threads) differs from this host, so all deltas are indicative only. On this host |delta| below about 1% is noise. The 12-thread runs put 12 threads on 8 vCPUs.

## Re-profile of the baseline

`profile.rs` is `baseline.rs` with timers added by `tools/mkprof.py` (SHA-256 `cae6db8f...`): `PHASE` stamps around the existing phases, `rdtsc` accumulators inside `for_each_doc` and `scan_chunk` in the `SCAN` line format of `experiments/b-linux-profile/run.py`, per-kind Boolean query time (`QKIND`) and cycle counters for parts of `boolean()` (`INFO`). `profile-candidate.rs` is the same instrumentation on `candidate.rs`. `reports/profile-lean-t8.json` and `reports/profile-final-t8.json`: 1 warmup plus 7 runs at 8 threads, interleaved with the uninstrumented binary; instrumentation overhead +5.0% and +3.8% wall. A first version also counted token classes per token (`reports/profile-lean-classes-t8.json`, +20% overhead, outside the timed parts); it was dropped because of that overhead.

Main thread phases (ms, medians):

| Phase | baseline | candidate |
| --- | ---: | ---: |
| parse/intern (serial) | 12.79 | 8.08 |
| sample scan + filter build (serial) | 2.35 | 2.09 |
| plan build (serial) | 4.09 | 3.38 |
| index (parallel) | 163.16 | 134.78 |
| answer (parallel) | 28.94 | 29.41 |
| serial total | 22.19 | 15.87 |
| main total | 216.66 | 180.78 |

Index scan split, cycles per token summed over threads (36,276,657 tokens; TSC 2.40 cycles/ns; 0.8% and 1.0% unattributed):

| Part | What it covers | baseline c/token | share | candidate c/token | share |
| --- | --- | ---: | ---: | ---: | ---: |
| masks | tab search, AVX2 masks, token bounds, key, hash, filter, slot prefetch, staging push | 38.0 | 45.0% | 30.9 | 45.0% |
| lookup | slot probe and `tokens` extend | 15.6 | 18.6% | 16.6 | 23.7% |
| callback | bitmap group bits, u16 stream, anchors (minus phrase) | 18.7 | 22.0% | 9.6 | 14.0% |
| phrase | anchor prefetch and compare | 3.7 | 4.4% | 3.5 | 5.1% |
| release | `madvise` every 1 MiB | 0.8 | 0.9% | 0.8 | 1.1% |
| csr | counting sort, dedup, gap closing | 7.6 | 9.0% | 7.5 | 10.9% |

Compared with the dddc0ea profile, lookup has shrunk (the filter) and masks is now the largest part. A diagnostic split of the masks part on step 3 (`reports/screen-ct.txt`, binaries with deliberately wrong output, cycles per token): token bounds plus staging push 10.4, plus key 16.0, plus hash and home slot 18.8, plus filter and select 25.6, then the slot prefetch and real lookups bring it to 30.8.

Answer phase, summed over threads (ms): bool_list 94.6 (20,690 queries), bool_list_bm 61.4 (3,730), bool_row_bm 51.2 (4,026), bool_row_list 14.0 (2,554). Inside `boolean()`: emitting a bitmap result (count, id sum, first ten, clear) 46.5 ms, materializing `tl` from the chunk lists 41.1 ms (42,296,407 ids), the per-clause `df` sum 7.3 ms, the probe path 9.4 ms. The answer phase is about 13% of main for the baseline and 16% for the candidate; none of the answer changes tried here beat noise (below).

Serial parse/intern, diagnostic split (temporary timers in diagnostic builds; console output, only the last one is saved in `reports/screen-ct.txt`): on step 3, the two-level `split` over lines and words alone took about 3.7 ms of the 13.2 ms (a single-pass `position` loop also 3.2 ms, consistent with a mispredicted branch at every word end), the key from a padded copy (a `memcpy` call per term) about 1 ms, and the rest is the intern probes into the cold 3 MB table and the per-query `Vec`s. On step 4, tokenizing all of `queries.txt` took 0.97 ms and tokenizing plus building one `Vec` per query 3.75 ms, so the 50,000 small `Vec`s cost about 2.8 ms; step 5 removes them.

## Kept changes

Each step is a patch in `steps/`, applied in order to `baseline.rs` (`patch baseline.rs < steps/1-...patch`, and so on) gives `candidate.rs`. Paired results are 1 warmup plus N measured pairs at 8 threads against the previous step, unless noted.

| Step | Change | S | S delta | break-even (0.3 x S%) | Paired wall | Wins | Paired CPU | Max RSS cand / base KiB | Report |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| 1 | branch-free bitmap group write | 565 | -2 | n/a | **-7.43%** (vs baseline) | 11/11 | -7.64% | 64,772 / 64,984 | `vA-t8.json` |
| 2 | branch-free filter select | 566 | +1 (+0.18%) | 0.05% | **-1.22%** | 8/11 | -1.06% | 65,076 / 64,676 | `vC1-vs-vA-t8.json` |
| 3 | token key mask from a 32-byte window | 566 | 0 | n/a | **-5.67%** | 11/11 | -6.56% | 64,840 / 64,748 | `vk2-vs-vC1-t8.json` |
| 4 | query parse with the scan tokenizer | 572 | +6 (+1.06%) | 0.32% | -0.86% | 7/11 | +0.67% | 64,604 / 64,728 | `vL-vs-vG-t8.json` |
| 4+5 | plus one flat term list for all queries | 558 | -8 vs step 3 | n/a | **-2.08%** (vs step 3) | 8/11 | +0.93% | 63,000 / 64,804 | `vN-vs-vG-t8.json` |
| 6 | `sort_unstable_by_key` for the BOOL term ranking | 558 | 0 | n/a | not timed separately | | | | |
| 7 | comments only | 558 | 0 | n/a | | | | | |

1. **Branch-free bitmap group write.** In the scan callback, `if let Some(g) = group.get_mut(t - nl) { *g |= bit }` was a data-dependent branch taken by the 44.6% of tokens that are bitmap terms, in random order. `group` now has one spare word after the `nbm` bitmap words, and every token ORs its bit into `group[(t - nl).min(nbm)]`; `flush` stores only `group[..nbm]`. Callback cycles per token fell from 18.7 to about 10. A variant with four spare words chosen by position (to break the store-to-load chain through the single spare word) was not faster (`rejected/vA2-four-spare-words.patch`, +0.72%, 3/11).
2. **Branch-free filter select.** The `if miss { ([0; 2], plan.empty) } else { (k, h) }` select of b-filter-parse compiled to a branch on the filter bit (about 21% of tokens miss, unpredictably). It is now a mask: `miss` is all ones for a short token whose filter bit is clear, the key is ANDed with `!miss` and the slot is `h ^ (h ^ plan.empty) & miss`. The generated code has no branch there (checked in the disassembly). Same semantics: a missed token is still looked up as the empty key at `plan.empty`.
3. **Token key mask from a 32-byte window.** `key()` built each 8-byte half's mask with a u128 shift of a saturated, clamped byte count (about 20 instructions with spills). It now loads the 16 bytes as one u128, ORs 0x20 and ANDs with `ONES[16 - n.min(16)..][..16]`, a constant of 16 0xff bytes followed by 16 zero bytes. n = 0 still gives a zero key, n >= 16 keeps all 16 bytes. Masks cycles per token 35.6 to 30.8. The 11-pair wall screen was of a 4-line form (`rejected/vk2-window-mask-4line.patch`, S 567); the committed 3-line form is the same computation (scan cycles 68.2 vs 68.1 per token in `screen-ct.txt`). Two other mask forms on the same base were not faster: u128 `checked_shr` (`vk1`/`vB1`, 74.7 c/token, and -0.21% wall, 7/11 in `vB1-vs-vA-t8.json`) and u64 `checked_shr` per half (`vk3`, 74.5 c/token).
4. **Query parse with the scan tokenizer.** The 64-byte token loop of `for_each_doc` moved into `each_token(data, i, f)`, which calls `f(s, e)` per token of one line and returns the next line start (or a position past the end, so a query file without a final LF still parses). `for_each_doc` calls it with the same key, filter and prefetch closure (inlined; no call in the disassembly). The query parse calls it too: per spec 2.3 the terms are lowercase, so a token starting with `B` or `P` starts a query, `A`, `O`, `N` are operators, anything else is a term. `intern` takes `(data, s, e)` so the key reads straight from `queries.txt` instead of a padded copy. Parse/intern 13.4 to 10.0 ms.
5. **One flat term list for all queries.** `enum Query` with a `Vec` per query (50,000 allocations), `remap()` and the unused `Plan::queries` field are gone. All terms are in one `Vec<(u8, u32)>` (operator byte, term; phrase terms carry 0), and query i is `qs[i] = (b'B' or b'P', its first term)` with a sentinel; `query(i)` returns the kind and the term slice. The renumbering is one `iter_mut`, the anchoring loop and the answer loop read `query(i)`, and `boolean()` is unchanged. The first BOOL term has operator 0, which `boolean()` treats as OR on the empty set like the former leading `B` of "BOOL" (`std::mem::take(&mut op)` resets it after each term). Parse/intern 10.0 to 8.15 ms, max RSS about 1.8 MB lower, S -14.
6. **Unstable sort of the BOOL terms by sample frequency.** Ties only decide which equal-frequency terms are numbered first and, when there are more than 65,535 BOOL terms, which of them get a bitmap; both representations give exact sets, so the output does not depend on it. 0 S lines; the sort was 0.68 ms of serial time.

## Tried and rejected

| Variant (patch in `rejected/`) | Base | Measurement | Decision |
| --- | --- | --- | --- |
| `vA2`: four spare group words by position | step 1 | +0.72% wall (3/11), `vA2-vs-vA-t8.json` | not faster |
| `vB1`, `vk1`: u128 `checked_shr` key mask | step 1 / 2 | -0.21% (7/11), `vB1-vs-vA-t8.json`; 74.7 vs 74.9 c/token | noise, +1 S |
| `vk3`: per-half u64 `checked_shr` mask | step 2 | 74.5 vs 74.9 c/token | noise |
| `vE3`: `nchunks = (3 * nthreads).max(...)` | step 2 | t8 +1.18% (2/9), RSS +1.5 MB; t6 -1.53% (6/9) but t6 is 18 chunks either way | slower at 8, noise at 6 |
| `vE4`: 4 chunks per thread | step 2 | t8 +3.26% (0/9), CPU +2.62%, RSS +1.9 MB; t6 +1.70% (2/9) | slower: per-chunk CSR setup and per-chunk answer work grow |
| `vE1`: chunks of up to 32 MiB (8 at 8 threads) | step 2 | t8 -2.36% (8/9) but max RSS 73,988 vs 64,740 KiB (+14%); t6 +3.64% (3/9) | RSS cost (M^-0.2) exceeds the gain, slower at 6 |
| `vF05`/`vF1`/`vF2`: bitmap spill at words/2, words, 2 x words (was words/4) | step 2 | wall +2.41%, +0.37%, -1.56% (9 pairs each); answer phase 28.6 / 29.1 / 30.0 ms vs 28.6 ms (`screen-ct.txt`) | answer time unchanged: less bitmap emit, more list merging |
| `vI0`: no slot prefetch | step 3 | 70.5 vs 69.9 c/token (masks -3.7, lookup +4.2) | neutral, as in b-lean |
| `vJ`: reinsert the table in sample-frequency order after renumbering | step 3 | lookup 15.6 to 14.3 c/token, CPU -2.59%, but wall +0.62% (5/11): plan build 4.1 to 8.6 ms serial (console) and max RSS +4.5 MB | rejected |
| `vK`: one pass moving sample-seen terms to free home slots | step 3 | 69.7 vs 69.9 c/token | no gain, +7 S |
| `vH1`: skip the no-op `copy_within` when no repeat was dropped | step 3 | 68.9 vs 68.5 c/token (console, not saved) | gap closing is not the CSR cost |
| `vM`: CSR dedup from a per-list last-document array, branch-free fill | step 4 | 70.3 vs 71.4 c/token, CSR 7.4 vs 7.8 | within noise, +1 S and a 130 KB array per chunk |

Not attempted, with reasons: a precomputed per-term `df` (7.3 ms summed over threads, at most about 0.5% wall, needs a stored vector); iterating chunk lists instead of materializing `tl` (the ids are read either way; 2.3 cycles per id); an AVX2 byte-level bitmap emit (could save about half of the 46.5 ms summed emit time but needs an intrinsics block plus a portable fallback, about 20 S lines); a parallel query parse (rejected in b-filter-parse). A diagnostic CSR fill without the dedup check changed the seed-1 hash, so the dedup is needed on seed 1 as well (not investigated further); it stays.

## Correctness

- Full seed 1: every warmup and measured run in every report produced `f86973c210228141bcb6f1f1b10188ad2a9b65f71e7cd7cf4590b38de4e80927` (asserted by `run.py`); every kept step and rejected variant (except the labeled diagnostics) was checked against it when built.
- `experiments/b-filter-parse/check_all.sh` (20 tiny seeds, sample seeds 2, 3, 4, 5, 7 and the edge fixtures, compared byte for byte with `official/reference/b_index.py`): pass=34 fail=0 xfail=2 at the default thread count, at 1 and at 12 threads. The xfails are `edge/no_lf` and `edge/no_lf_docs` (`docs.txt` without a trailing LF, outside spec 2.1), unchanged from the baseline. `edge/no_lf_queries`, `opwords` (lowercase `and`, `or`, `not` as terms), `upper`, `repeat` and `many_terms` pass.
- The x86-64-v3 release build and the portable build (`RUSTFLAGS='-Ctarget-cpu=x86-64' cargo build --release --target-dir /projects/sandbox/.data/tgt-generic`) compile without warnings; the portable binary has no ymm instructions and also passes check_all (pass=34).
- The query parse relies on the spec 2.3 grammar (terms are `[a-z0-9]+`, operators uppercase, single spaces); a malformed line starting with a term would panic instead of being misread.

## Files

| File | Content |
| --- | --- |
| `baseline.rs`, `candidate.rs` | sources (SHA-256 above) |
| `profile.rs`, `profile-candidate.rs` | instrumented copies (not for production) made by `tools/mkprof.py` |
| `steps/*.patch` | the kept steps, in order |
| `rejected/*.patch` | rejected variants against the step named in the table |
| `reports/final-t8.json`, `final-t6.json`, `final-t12.json` | final 21-pair reports vs `lean-final` |
| `reports/v*-*.json` | screening reports from the tables above |
| `reports/profile-*.json`, `prof-vC1-t8.json` | instrumented runs (baseline, after step 2, candidate) |
| `reports/screen-ct.txt` | console output of `tools/ct.py` (scan cycles per token) and `tools/phases.py` (phase ms) screens |
| `tools/` | `mkprof.py` (instrumentation), `ct.py`, `phases.py`, `build.sh` (build a source to `.data/bin/<name>` and print the hash prefix), `ab.sh` (paired run plus `pair.py`); paths assume `/projects/sandbox/.data` |

## Reproduce

```sh
D=/projects/sandbox/.data; E=experiments/b-speed3
build() { cp $1 track-b/src/main.rs && touch track-b/src/main.rs &&
  (cd track-b && RUSTFLAGS='-Ctarget-cpu=x86-64-v3' cargo build --release) && cp track-b/target/release/solution $D/bin/$2; }
build $E/baseline.rs lean-final
build $E/candidate.rs s3-final
for t in "" 1 12; do experiments/b-filter-parse/check_all.sh $D/bin/s3-final $t 2>/dev/null; done
for t in 8 6 12; do
  python3 experiments/b-linux-profile/run.py --binary $D/bin/s3-final --baseline $D/bin/lean-final \
    --data $D/speed-b-full --runs 21 --threads $t --report $D/final-t$t.json
done
python3 experiments/b-filter-parse/pair.py $D/final-t*.json
python3 $E/tools/mkprof.py $E/candidate.rs > $D/p.rs && build $D/p.rs p-final   # instrumented
for f in $E/baseline.rs $E/candidate.rs; do rustfmt --edition 2021 --emit stdout $f | grep -cvE '^\s*$|^\s*//'; done
```
