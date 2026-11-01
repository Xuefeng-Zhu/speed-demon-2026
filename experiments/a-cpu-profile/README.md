# Track A CPU attribution at e4308ed, and newline-mask line stepping (kept)

`base.rs` is production `track-a/src/main.rs` at `e4308ed`, the same source as `171ca6f` (trimmed, board S 414). This profile looks at CPU time only. Local wall-time results that depend on the kernel or the allocator did not carry over to the board (see `experiments/a-profile-2/README.md`), so everything here runs on one thread (`SD_THREADS=1`): there is no lock, page-fault or hyperthread contention, and the numbers count work, not waiting. Local x86 VM (Xeon Platinum 8488C); these are not official scores.

`cpu.rs` adds `CLOCK_THREAD_CPUTIME_ID` timers around the parse and the summary sub-phases, plus `--cfg mode="..."` switches that skip work (diagnostic only; outputs are wrong in those modes, and parse-only modes exit after parsing). `--cfg pop` maps the whole file with `MAP_POPULATE` before the timers start. `attribute.py ROUNDS THREADS` runs every mode in shuffled rounds and writes `attribute-1.json`.

## Where the CPU time goes (one thread, medians of 20 rounds, ms)

The whole run takes about 118 ms on one thread: parse 93.7 ms and summary 23.7 ms.

| Parse mode | What runs | Parse CPU | Without file page faults (`pop`) |
|---|---|---:|---:|
| `lines` | only steps from newline to newline (8-byte loads in a dependent chain) | 63.9 | 57.8 |
| `fields` | plus hour, endpoint scan and latency | 74.0 | 66.1 |
| `scan` | plus the endpoint hash | 74.4 | |
| `notable` | plus the record push, no endpoint table | 83.9 | 77.5 |
| `nopush` | everything except the record push | 69.9 | 63.3 |
| `full` | production | 93.7 | 87.5 |

- **File page faults** cost about 6 ms (`full` 93.7 vs `full-pop` 87.5), and `MADV_DONTNEED` 2.9 ms. Together that is about 8% of the run.
- **The costs do not add up.** Dropping the table from `full` saves 9.8 ms, while dropping the push saves 23.8 ms, yet adding the push to `scan` costs only 9.5 ms, and `nopush` is cheaper than `scan`. The loop's speed is set by one dependency chain, not by the sum of its parts. Each line's start was known only after its latency had been parsed (`parse_latency` returned the next line's offset), so the next line's loads could not begin early. In `lines` mode alone, the 8-byte newline search in that chain costs 64 ms.

| Summary part | CPU |
|---|---:|
| count pass over the records | 3.2 |
| group offsets | 0.2 |
| latency scatter | 5.0 |
| groups: percentiles and formatting | 15.3 |
| of which: percentiles for groups of up to 64 values | 3.2 (`nosmall` 12.1) |
| of which: percentiles for larger groups | 6.3 (`nobig` 9.0) |
| of which: formatting | 6.3 (`nofmt` 9.0) |

## Newline-mask line stepping (`nlmask.rs`, kept)

The parser now keeps a 64-bit mask of the newlines in the current 64-byte block, built with the same AVX2 `eq_mask` as the endpoint scan. Each line's end comes from the lowest set bit, and a new block is scanned once its mask is used up. The next line's start no longer depends on parsing this line's latency, so consecutive lines overlap in the CPU. `parse_latency` now takes the digit count from the known line end; 8-digit latencies use the SWAR path too, and longer ones keep the scalar loop. The lines changed from 407 to 414 (`experiments/a-trim/sloc.py`).

| `nlmask` / `base` paired median | 1 thread | 8 threads | 12 threads | 20 threads | Report |
|---|---:|---:|---:|---:|---|
| 31 rounds, seed 1301 | 0.8300 | 0.9524 | 0.9614 | 0.9442 | `bench-nlmask.json` |
| 61 rounds, seed 1302 | 0.8293 | 0.9593 | 0.9509 | 0.9700 | `bench-nlmask-2.json` |

On one thread the whole run drops from 118.7 to 98.2 ms, so about 20 ms of CPU disappears. With 8 to 20 threads on this 4-core VM the gain is 3 to 5%, since there the run is bounded more by memory bandwidth and by two hyperthreads sharing a core. This is a pure CPU change (fewer stalls in one thread's instruction stream), which is the kind of local evidence that carried over to the board before (PR #4, #10).

Correctness: `check.py` 14 of 14 and `adversarial.py --spec` 0 failures, for both `nlmask.rs` and the production copy `final.rs` (the same code with the `eq_mask` comment updated for the new caller). Reads stay in bounds: each newline-block scan starts at a 64-byte block that holds the end of an unparsed line, so it ends at most 64 bytes past the last line, inside the 4 KiB zero pad.

## What is left (one thread, after `nlmask`)

About 98 ms in total. In order of size:

- walking the bytes, including about 9 ms of page faults and `madvise`;
- the summary, about 24 ms: percentiles 9.5, formatting 6.3, scatter 5.0, count 3.2;
- the endpoint table and the record push, about 10 ms each before this change.

Their share after `nlmask` has not been re-measured.
