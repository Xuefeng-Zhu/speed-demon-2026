# Track B line trim without behaviour change

`baseline.rs` and `baseline.Dockerfile` are `track-b/src/main.rs` and `track-b/Dockerfile` at `speed-demon` `f828bd8` (source SHA-256 `d3920254...66b9`). `candidate.rs` and `candidate.Dockerfile` are the trimmed files (source SHA-256 `c2b53298...cb1e`). The algorithm, thresholds, prefetching and hot loops are unchanged. The source is formatted with default `rustfmt --edition 2021`, so what is written is what is counted.

## How S is counted

`sloc.py` (copy of the tool used for A and D) formats `main.rs` with default rustfmt and counts non-blank lines that do not start with `//`, then adds the non-blank Dockerfile lines. For `f828bd8` it gives 557 + 26 = 583, the board's S for B. Doc comments (`///`, `//!`) do not count and are kept.

| | Code lines | Dockerfile lines | S |
|---|---:|---:|---:|
| `baseline` | 557 | 26 | 583 |
| `candidate` | 501 | 18 | 519 |

S drops by 64 lines (-11.0%), worth about +1.8% K from `(583 / 519)^0.15` at equal T and M. The keep rule allows T up to `(583 / 519)^0.3` = 1.036 times the baseline.

## Edits

- `masks` loses its scalar fallback and `prefetch` its aarch64 branch. The crate's `.cargo/config.toml` pins `target-cpu=x86-64-v3` and the Dockerfile asserts x86-64 with AVX2, so the AVX2 code is the only one ever built for the board (as in the A trim). `std::arch::x86_64::*` is imported once. The source no longer builds for aarch64.
- `par` now does the dynamic claiming itself: n threads claim k in 0..m from one atomic counter, each with its own `Default` state, and the results come back in order of k. Both callers (chunk scan and query blocks) lose their `claim` closures, the `flatten` / sort / unzip chains, and the counter reset.
- `scan_chunk` returns its phrase matches next to the `Chunk` (`type Hits`) instead of in a field, so the struct literal fits on one line. Hits are concatenated in chunk order, then sorted and deduplicated as before.
- `Scratch` is a tuple type `(list, term list, merge output, bitmap)`, destructured once in `boolean`. Each query thread sizes the bitmap on its first block (`resize`, a no-op afterwards) instead of at thread start.
- The phrase-hit slice uses one `at(qi)` partition-point closure (`at(qi)..at(qi + 1)` is the same range as before).
- `id_at` folds its empty-last-chunk case into a `then_some`; `nthreads` imports `available_parallelism`; `bools`, the bitmap role flip and the renumbering loop name closures so rustfmt keeps them on one line; `rows` is built from the `ManuallyDrop` vector named `bm` so the line fits.
- Dockerfile: the 16 continuation lines of the PGO `RUN` are joined into 8 lines by phase (CPU checks, instrumented build, training run, profdata lookup, merge, profile summary check, optimized build). The `;`-separated commands, their order and their text are unchanged.

## Checks (8-vCPU sandbox, x86-64-v3, no PGO; local measurements, not board results)

- Full seed 1 matched the published SHA-256 `f86973c2...0927` at `SD_THREADS` 1, 8 and 12 and in every timing run.
- `smallcheck.py b`: tiny and sample at seeds 2 and 7 match the official reference at default, 1 and 12 threads.
- `experiments/b-filter-parse/check_all.sh`: pass=34 fail=0 xfail=2 at default, 1 and 12 threads (the two xfails are the pre-existing no-trailing-LF `docs.txt` fixtures).
- Dockerfile: `official/harness/dockerfile_check.py` passes against `official/harness/allowlist.json`. The joined logical instructions (from the checker's own `logical_lines`) are identical to the baseline's after whitespace normalisation, and `sh -n` accepts the RUN script. Docker cannot run here (podman without conmon). The RUN script was also run natively with paths rewritten: CPU checks, instrumented build, training run and profdata lookup passed; the merge step failed only because the system `llvm-profdata` cannot read rustc 1.92's profraw format, which does not apply to the board's image.
- Speed, `memrun.py` interleaved runs after warmup against `/projects/sandbox/.data/bin/base-b` (the `f828bd8` build):

| Threads | Pairs | Baseline median | Candidate median | Median paired ratio | Wins | est M base / cand |
|---|---:|---:|---:|---:|---:|---:|
| default (8) | 25 | 227.6 ms | 221.5 ms | 0.970 | 20/25 | 62.43 / 62.42 MB |
| 12 | 21 | 231.1 ms | 223.8 ms | 0.973 | 19/21 | 67.55 / 66.97 MB |

The candidate is at least as fast as the baseline. The roughly 3% gain was not expected from these edits and may be code layout; the claim is only "not slower". Reports: `reports/trim-b-t8.json`, `reports/trim-b-t12.json`. The disassembly is about the same size (91,942 vs 91,926 lines).

Board run pending.

## Reproduce

```sh
cd track-b && RUSTFLAGS='-Ctarget-cpu=x86-64-v3' cargo build --release
python3 experiments/b-trim/sloc.py b
SD_DATA=<b-full> SD_OUT=/tmp/o track-b/target/release/solution && sha256sum /tmp/o/results.txt
sh experiments/b-filter-parse/check_all.sh track-b/target/release/solution 12
python3 official/harness/dockerfile_check.py track-b/Dockerfile official/harness/allowlist.json
```

## Overlap with other branches

`b-mem2` and `b-pure` edit the same functions of `track-b/src/main.rs` (`scan_chunk`, the counting sort, the query parse). The branches are separate board trials off `f828bd8` and are not rebased onto each other here. Whichever lands after another must be rebased, rebuilt, re-hashed (full seed 1 and `check_all.sh`) and re-counted: S 519 here and S 586 there are both relative to the untrimmed base.
