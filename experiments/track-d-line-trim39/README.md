# D line trim without behaviour change

`baseline.rs` is `track-d/src/main.rs` at `c935438`, the same D source as `804a03c`. `make_trim.py SRC OUT` applies the edits. The candidate in `track-d/src/main.rs` is its output after default `rustfmt --edition 2021`. `count_s.py REV...` prints, for each commit, the number of non-blank, non-comment lines before and after default rustfmt.

## How S is counted

| Commit | Board S | As written | After default rustfmt | Dockerfile non-blank lines |
|---|---:|---:|---:|---:|
| `ccbfbc0` | 390 | 351 | 383 | 7 |
| `dbab6be` | 410 | 379 | 403 | 7 |
| `804a03c` | 407 | 378 | 400 | 7 |

Board S matches the rustfmt-formatted code lines of `main.rs` plus the 7 non-blank Dockerfile lines in all three cases. The official harness files in this repository do not document the rule, so this is an inference. Either way, lines that only look short because they exceed rustfmt's width are counted at their formatted length. The old source had eight such lines, costing 22 lines on the board.

## Edits

- Source formatted with default rustfmt, so what is written is what is counted (`cargo fmt --check` now passes).
- `each_edge` inlined into the parse loop; `cut(i)` computed per thread instead of a `cuts` vector; `line_end` written with `find`.
- `std::mem::take` imported; the bucket index `(e >> 32) - j * block_len` named once as `at`.
- `ends`: the per-chunk sum named as a closure, so the `parallel` call fits on one line.
- `claim` uses `fetch_max(1)` instead of `compare_exchange(0, 1)`. A claimed slot always holds 1 or a complemented id, both non-zero, so raising it to at least 1 claims it only if it was 0. The pre-check load is kept.
- `Side::new` binds the heap fields first, so the struct literal fits on one line.

Formatted code lines in `main.rs` went from 400 to 376, so board S should go from 407 to about 383. That is worth about +0.9% K, from `(407 / 383)^0.15`.

## Checks (8-thread sandbox, not board numbers)

- Full seed 1 matched the published SHA-256.
- 25 alternating runs: baseline 175.5 ms median (min 168.7), candidate 175.6 (169.4). A 21-run batch of an earlier step of the same trim gave 172.8 against 173.0.
- An overflow- and debug-checked build passed the random, exhaustive, threshold, 2^21 boundary, extreme and same-bucket suites (see `../track-d-coarse-radix33/README.md`).

## Tried and not kept

- Inlining `relabel`'s `span` and replacing the `owners` loop in `Side::clear` with `for_each`: rustfmt split the results across more lines, so neither saved anything.
- Replacing the parallel prefix sum `ends` with a sequential one would save about 7 lines but cost an estimated 0.5–1 ms, roughly cancelling out on K. Not done.
