# Track A x86: parse breakdown and current-hour record cursor

`base.rs` is the production `track-a/src/main.rs` at `b607e9e` (after PR #4). Local x86 VM only (8 vCPU Xeon Platinum 8488C, 4 cores x 2 hyperthreads); not official scores. 20 threads oversubscribes this VM and is only a regression check for the scoring box's 20 hardware threads.

## Parse breakdown

`breakdown.rs` is `base.rs` with `--cfg mode="..."` switches that skip work (diagnostic only; outputs are wrong in these modes). Timed with `experiments/a-x86-speed/parse-time.py`, 8 threads, 31 interleaved rounds. Reports: `parse-breakdown.json`, `parse-flat.json`, `parse-huge.json`.

| Mode | What it does | Parse wall median |
|---|---|---:|
| `full` | production | 20.46 ms |
| `lines` | only hops from newline to newline | 9.85 ms |
| `scan` | hour, endpoint scan and hash, latency; no table, no push | 11.69 ms |
| `notable` | `scan` plus record push, no endpoint table | 15.59 ms |
| `nopush` | everything except the record push | 15.59 ms |
| `nomadv` | no `MADV_DONTNEED` | 18.45 ms |
| `flat` (second run, full 19.92) | push to one preallocated per-thread vector instead of 72 hour vectors | 17.54 ms |
| `flathuge` (third run, full 19.66) | `flat` with `MADV_HUGEPAGE` on the vector | 17.71 ms |

Reading it: about 10 ms is walking the bytes, the endpoint table is about 4 ms, and the record push is about 4 to 5 ms. Pushing into one flat vector saves about 2.4 ms of the push, so roughly half the push cost is the hour indexing, not the memory writes. Huge pages did not help (THP is `madvise` mode on this host). `madvise` costs about 2 ms of parse time, but removing it end to end is slower (below), because the pages are then unmapped at exit on one thread.

On seed 1 only 1,054 of 3,100,000 consecutive line pairs change hour (0.034%). The spec promises no ordering bound, so this can only be a fast path. Correctness never depends on it.

## Candidates

- `curhour.rs`: the current hour's record pair is swapped out of `hours` into a local and swapped back when the hour changes.
- `cursor.rs`: `curhour` plus the record vector's length kept in a local (`n`) and written with a raw pointer. The length is stored back only on an hour change, on growth and at the end, so the hot loop has no `Vec::push` length and capacity reloads.
- `nomadv.rs`: production after this change, without the per-chunk `MADV_DONTNEED`.

All candidates passed `experiments/a-x86-speed/check.py` (14 of 14) and `adversarial.py` with 0 failures. Production with `cursor` also passed `adversarial.py --quick` on a scalar (no AVX2) build.

| Candidate vs `base` | 8 threads | 12 threads | 20 threads | Report |
|---|---:|---:|---:|---|
| `curhour` (41 rounds, seed 801) | 0.9787 | 0.9760 | 0.9947 | `bench-1.json` |
| `cursor` (41 rounds, seed 801) | 0.9673 | 0.9711 | 0.9741 | `bench-1.json` |
| `cursor` repeat (61 rounds, seed 802) | 0.9787 | 0.9820 | 0.9780 | `bench-2.json` |
| `nomadv` vs `cursor-final` (41 rounds, seed 803) | 1.0496 | 1.0324 | 1.0255 | `bench-nomadv.json` |

`cursor` met the decision rule in both invocations (below 0.985 at 8 threads, no regression at 12) and is now production (`cursor-final.rs`, with growth reserving `n.max(1 << 15)` so a zero-capacity vector can never be written). `nomadv` is rejected.
