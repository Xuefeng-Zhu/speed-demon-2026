# Track A line trim (same speed, S 447 to 387)

`base.rs` is production `track-a/src/main.rs` at `speed-demon` (`12589c3d...`, after PR #4). `t4.rs` is the trimmed source and `t4.patch` is the diff between them. The patch is meant to be applied after the dynamic-chunking change, and it does not touch `main()` or the parse loop's chunk handling. It applies cleanly to `speed-demon` as of this commit (`git apply --check`).

## Line count

`sloc.py` formats a copy with `rustfmt --edition 2021` and counts non-blank lines that do not start with `//`. It gives 303 for the older `experiments/a-x86-speed/baseline.rs`, which matches the board's S=303 for that source. The board's own count may still differ by a few lines.

| Source | Code lines |
|---|---:|
| `base.rs` | 447 |
| `t1.rs` | 411 |
| `t2.rs` | 398 |
| `t3.rs` | 400 |
| `t4.rs` | 387 |

With S above Sref, 447 to 387 is worth (447/387)^0.15 = about +2.2% K at equal time and memory.

## What was removed

- `t1`: paths that only run on inputs outside the spec or off the x86-64-v3 build target.
  - The word-at-a-time endpoint scan past 128 bytes, the `memcmp` compare for names of 128 bytes or more, and the slow `format!` path for over-long lines. The spec caps endpoints at 125 bytes, and an over-long one now stops with an assert instead of being handled.
  - The scalar `eq_mask` fallback, the non-AVX2 summary dispatch, and the `sort_unstable` branch of `select_ranks`, which with AVX2 only ever receives groups larger than 64.
  - The build is pinned to `target-cpu=x86-64-v3` (`track-a/.cargo/config.toml`), so the AVX2 code is always compiled with AVX2. The source no longer builds on non-x86 targets, so an ARM Mac can no longer run it natively.
- `t2`: `t1` with number formatting one digit at a time instead of through a two-digit table.
- `t3`: `t1` with a fixed 4,096-slot endpoint table and no growth. The spec fixes 1,842 endpoints per seed, and an assert stops the program at 2,048 endpoints per thread instead of looping forever.
- `t4`: `t2` and `t3` together.

The comment the PR #4 review flagged on the 64-127 byte compare is reworded in all of them: the second read stays in bounds because the arena always ends with 64 zero bytes, and bytes past the name are masked off.

## Correctness

- All of `t1` to `t4` pass `experiments/a-x86-speed/check.py`, 14 of 14 checks: the full seed-1 hash at 1, 2, 3, 6, 8 and 12 threads and default, `test.py`, `page_end_test.py`, `latency_grid_test.py`, and sample seeds 2, 98, 999 and 4242 against the official reference.
- `adversarial.py` has a new `--spec` mode that keeps every input within the spec: endpoint lengths 1 to 125 including the shared-word families, a case with exactly 1,842 distinct endpoints, the latency boundaries and the group sizes. `t4` and production both pass it with 0 failures.
- Without `--spec`, `t4` stops on the 126- to 300-byte endpoints with its assert ("endpoint longer than the spec allows"). That is the intended behaviour; the input is outside the spec.

## Speed

Local x86 VM (8 vCPU Xeon Platinum 8488C), `bench.py`, paired median ratio candidate/base. These are not official scores.

| Variant | 8 threads | 12 threads | 20 threads | Report |
|---|---:|---:|---:|---|
| `t1` | 0.9762 | 0.9861 | 1.0128 | `bench-1.json` (41 rounds, seed 901) |
| `t2` | 0.9743 | 0.9979 | 0.9895 | `bench-1.json` |
| `t3` | 0.9557 | 0.9970 | 0.9961 | `bench-1.json` |
| `t4` | 0.9887 | 0.9929 | 0.9941 | `bench-1.json` |
| `t4` repeat | 0.9812 | 0.9993 | 0.9924 | `bench-2.json` (61 rounds, seed 902) |

`t4` is at least as fast as `base` everywhere; the small differences are within the A/A band of about ±1.5%.

## Applying

```sh
git apply -p1 experiments/a-trim/t4.patch   # from the repo root, after the chunking change
python3 experiments/a-x86-speed/check.py track-a/target/release/solution
python3 experiments/a-x86-speed/adversarial.py --binary track-a/target/release/solution --spec
python3 experiments/a-trim/sloc.py track-a/src/main.rs
```

If the parse loop has changed, the two hunks in `parse` (the 128-byte scan) may need to be applied by hand. The other hunks touch only `eq_mask`, `Table`, `put_num`, `small_ranks`, `select_ranks` and `summarize`.
