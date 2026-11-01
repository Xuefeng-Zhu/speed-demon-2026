# Track A board probes: measuring where the box spends T

Two local gains in a row, PR #19 (kernel lock waits) and PR #21 (parse CPU), did not show up on the board. The local VM (4 cores x 2 hyperthreads, Linux 6.1) no longer predicts where the scoring box (6 P-cores with hyperthreading plus 8 E-cores, 20 threads) spends its time. Each probe here is production `track-a/src/main.rs` at `80882e1` (`base.rs`) with one change, as a full source file and as a patch against that commit. Every probe writes the correct `summary.txt`: all pass the full seed-1 hash at 1 and 8 threads and at the default thread count, the three verification scripts, and sample seed 999 against the reference (`check.py --threads 1,8,default --seeds 999`).

**Use:** apply one patch per board run (`git apply -p1 experiments/a-box-probes/<probe>.patch`), record T, then revert. The probes are deliberately no faster, and two of them are slower. They are for practice runs only and are never meant to be kept.

| Probe | Change | What the board result tells us |
|---|---|---|
| `stderr` | One `sd_phases ...` line on stderr at exit, with ms since the start of `main` for: mapping, thread spawn, first / median / last parse thread done, barrier, plan, first / last summary worker done, last write, end. | If the board shows stderr or run logs, a single run gives the full phase breakdown and the other probes are not needed. Locally it costs nothing measurable (paired 0.988 at 8 threads, 1.005 at 20). |
| `threads8`, `threads12`, `threads14` | Default thread count capped at 8, 12 or 14 instead of all 20 hardware threads | Whether more threads help on the box. If 12 or 14 is faster, the box is limited by memory bandwidth, by two hyperthreads sharing a core, or by slow E-core chunks the others wait for at the barrier (the parse split is equal-sized). |
| `parse2` | Each parse thread parses its chunk twice and discards the first result | The increase in T is about the box's parse wall time. |
| `sum2` | Every hour is summarized twice (on a copy of its records) and the first result discarded | The increase in T is about the box's summary wall time. |

Local calibration (`local-calibration.json`, 21 rounds, seed 1401; local VM, not official scores):

| Threads | base | `stderr` | `parse2` | `sum2` | Phase times from `stderr` |
|---:|---:|---:|---:|---:|---|
| 8 | 28.9 ms | 28.6 ms | 45.9 ms (+17.0) | 33.1 ms (+4.2) | parse done 21.4, summary done 28.1 |
| 20 | 41.3 ms | 41.8 ms | 64.3 ms (+23.0) | 50.4 ms (+9.1) | |

On this VM, `parse2` adds about 80% of the parse phase (17.0 of about 21 ms at 8 threads) and `sum2` about 60% of the summary phase (4.2 of about 6.7 ms). The second pass runs with warm caches and tables, and the phases include some waiting. Read the box's increases as lower bounds of its phase times.

Suggested order on the board: `stderr` first, which settles everything if stderr is visible. Otherwise run `threads12` and `threads14`, which could also simply be faster, then `parse2` and `sum2`.
