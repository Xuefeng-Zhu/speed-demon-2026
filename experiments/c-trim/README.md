# Track C line trim without behaviour change

`baseline.rs` is `track-c/src/main.rs` at `speed-demon` `f828bd8` (SHA-256 `5f71f7b2...7d98`); `candidate.rs` is the trimmed source (SHA-256 `3fecb63c...fe17`), formatted with default `rustfmt --edition 2021`. The parse loop, the owner tables, thresholds and prefetching are unchanged.

## How S is counted

`sloc.py` (copy of the tool used for A, B and D) counts the non-blank lines of default rustfmt output that do not start with `//`, plus the non-blank Dockerfile lines. For `f828bd8` it gives 328 + 8 = 336.

| | Code lines | Dockerfile lines | S |
|---|---:|---:|---:|
| `baseline` | 328 | 8 | 336 |
| `candidate` | 295 | 7 | 302 |

S drops by 34 lines (-10.1%), worth about +1.6% K from `(336 / 302)^0.15` at equal T and M. The keep rule allows T up to `(336 / 302)^0.3` = 1.033 times the baseline.

## Edits

- `masks` loses its non-AVX2 fallback and `prefetch` its `cfg(target_arch)` guard. `.cargo/config.toml` pins `target-cpu=x86-64-v3` for x86-64, so the AVX2 path is the only one built for the board. The source no longer builds for other architectures.
- `par` (one caller) is inlined: the worker is the closure `work`, run on n scoped threads in `main`.
- Region split: `rcut(t)` finds the first line start at or after t/n of the way with one `position`, and `rcut(n)` is the end of the file because the last line ends with LF (spec 2.3), so the `t == 0` and `t + 1 == n` special cases go. `bound` drops its `c == chunks` arm: `cr(size)` returns `size`, so the general formula gives the same value (one extra zero-byte `pread` for the last chunk).
- The two region-pass number reads fit on one line (`code` takes the slice from the country onward and reads its first three bytes).
- Statements that rustfmt split are written to fit: the `last` region line, the `name_hash` fold (closure `mix`), the quote prefix XOR as `(0..6).fold(..)`, the end-of-chunk shift named `tail`, the quote count before a field named `before`, the slot prefetch in `mark` as `Option::map`, and paired `let`s for `(mine, used)`, `(agg, out)`, `(ring, r)` and `(start, chunks)`. A `Rec` type names the ring entry.
- Dockerfile: the leading comment line goes; the instructions are unchanged.

Tried and not kept: giving `finish` slice parameters (`&mut [Agg]`, `&mut [Vec<u64>]`) saved one more line, but it changed the worker's code (1,593 instead of 1,851 instructions in the thread body) and measured +0.7% to +4.5% in three interleaved batches (`reports/slice-r*.json`). With `&mut Vec` parameters the worker body is 1,854 instructions, against 1,851 for the baseline.

## Checks (8-vCPU sandbox, `-Ctarget-cpu=native`; local measurements, not board results)

- Full seed 1 matched the published SHA-256 `d8088b1c...f536` with all 8 CPUs and under `taskset` with 1, 3 and 6 CPUs (C sizes its threads from `available_parallelism`).
- `smallcheck.py c`: tiny and sample at seeds 2 and 7 match the official reference.
- `fixtures.py` (copied from `experiments/c-mem` on branch `c-mem`): long names, 15 to 100 KB records, header BOM, unterminated last record, many tiny records, tiny/sample seed 42, all match `official/reference/c_join.py` with 8 CPUs and under `taskset` with 1 and 3 CPUs. Its `--threads` sets `SD_THREADS`, which this build ignores, so the thread count was set with `taskset`.
- `official/harness/dockerfile_check.py` passes.
- Speed, `memrun.py` interleaved runs after warmup against `/projects/sandbox/.data/bin/base-c` (the `f828bd8` build); `base-c-aa` is a byte-identical copy of the baseline binary, an A/A control:

| Batch | Runs | Baseline median | Candidate median | Paired ratio | A/A ratio | Report |
|---|---:|---:|---:|---:|---:|---|
| r4 | 41 | 49.3 ms | 49.9 ms | 1.024 | | `reports/trim-c-r4.json` |
| r5 | 41 | 50.3 ms | 50.8 ms | 1.012 | 1.007 | `reports/trim-c-r5.json` |
| r6 | 61 | 50.1 ms | 50.0 ms | 1.004 | 1.002 | `reports/trim-c-r6.json` |

The candidate is within about 1% of the baseline, close to the A/A spread and well inside the 3.3% the S gain pays for. Estimated M is the same (9.4 to 9.5 MB).

Board run pending.

## Reproduce

```sh
cd track-c && RUSTFLAGS='-Ctarget-cpu=native' cargo build --release
python3 experiments/c-trim/sloc.py c
SD_DATA=<c-full> SD_OUT=/tmp/o track-c/target/release/solution && sha256sum /tmp/o/aggregates.txt
taskset -c 0 python3 experiments/c-trim/fixtures.py track-c/target/release/solution --threads 1
```
