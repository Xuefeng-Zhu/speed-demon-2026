# Track B speed5: less serial work before the scan

`baseline.rs` is production Track B, PR #48 (SHA-256 `1b5cdd57…`). `candidate.rs` is the proposed `track-b/src/main.rs` (SHA-256 `82f9199f…`). The plan, chunking, scan and answering are unchanged; the changes are in the single-threaded setup that runs before the workers start. All numbers are measurements on the profiling VM described in `experiments/b-speed4/README.md`, not board scores. Board run: pending.

## Why the serial part

A timeline of production #48 on the VM (`experiments/b-speed4/tl.py` and `tlrun.py`, seed 1, 12 threads, median of 7 runs) gives a wall of 125.4 ms:

| Phase | ms |
|---|---|
| Spawn to `main` | 1.3 |
| Parse and intern the queries | 6.7 |
| Filter build | 0.8 |
| Sample scan | 1.6 |
| Plan: renumber, phrases, cuts | 4.6 |
| Worker phase | 106.7 |
| Output and exit | 3.5 |

The workers are busy for 98% of their phase, wait 0 ms for the setup thread and idle 1.3 ms on average after their last chunk, so the wall is not lost to imbalance. Of the 13.7 ms before the workers start, `tlmain.py` attributes about 4 ms to page-fault system time. The plan phase alone took 1,048 page faults for vectors that live only during setup.

## What changed

- **Filter built while interning:** the filter bit of a short term is set when the term is first inserted. That removes the pass over all 131,072 table slots that built the filter after the parse (0.8 ms).
- **Term 0 for tokens no query uses:** the table's empty slots, being zero, already hold term 0, so they no longer need writing. Its number after renumbering is read back from the table's empty slot (`tbl[empty][2]`) instead of assumed to be the last id.
- **Renumbering in one loop, without the 600 KB `order` vector:** the new numbers, roles and sample frequencies are written directly.
- **Smaller phrase list:** each phrase is kept as (anchor, query, position), 12 instead of 40 bytes, and its terms are read back from the query when `phr` is built. `start` is `u32` instead of `u64`, and `phr` is reserved once.
- **One pass over the table:** it now gives each term both its new number and its phrases' start; production made two passes.

Main-thread setup on the VM (`tlmain.py`, median of 9 runs; wall, then page faults):

| Step | Production #48 | Candidate |
|---|---|---|
| Parse and intern | 6.65 ms, 501 | 6.76 ms, 535 |
| Filter build | 0.81 ms, 33 | 0 |
| Sample scan | 1.56 ms, 304 | 1.51 ms, 304 |
| Plan | 4.55 ms, 1,048 | 3.44 ms, 577 |
| Total before the workers start | 13.6 ms | 11.7 ms |

## Result

| Measurement | Production #48 | Candidate | Change |
|---|---|---|---|
| Official Dockerfile build, board `docker run` flags, 14 rounds, T | 132.2 ms (min 126.4) | 126.8 ms (min 124.8) | −1.2% (median of paired differences) |
| Same runs, cgroup `memory.peak`, median / max | 50.5 / 51.4 MB | 49.3 / 50.1 MB | −1.2 / −1.3 MB |
| Native PGO build, 30 rounds, seed 1 / seed 2 | 125.9 / 124.6 ms | 124.7 / 123.4 ms | −1.2% / −1.1% |
| Native, repeat of 30 rounds | 131.8 / 125.4 ms | 124.6 / 123.6 ms | −2.0% / −1.2% |
| Native, fresh cgroup per run, peak, seed 1 / seed 2 (6 rounds) | 50.8 / 48.9 MB | 48.7 / 47.4 MB | −2.1 / −1.5 MB |
| S, official `static_axes.py`: Rust lines | 691 | 685 | −6 (board S 717 → 711) |

M falls because the setup vectors that were dropped (`order`, the 40-byte phrase list, the `u64` `start`) had stayed resident in malloc's heap through the scan. `malloc_trim(0)` before the scan did not lower M further (49.1 / 47.2 MB median peaks), so the gain comes from not allocating them. If the board shows the same changes, K rises by about 1.1%: 1.006 from T, 1.005 from M and 1.001 from S.

## Measured and rejected

| Variant | Result |
|---|---|
| Parse split across 12 threads (tokenize and hash in parallel, intern serially with prefetch 16 terms ahead) | parse 6.7 → 6.2 ms for +14 lines; wall −2.3% / −1.5%, against −2.3% / −2.0% for the same build without it |
| Key computed once per term in the parse and passed to `intern` | no gain (−1.1% / −0.9%, against −2.2% / −1.8% for the same changes without it) |
| Sample of 256 KiB instead of 512 KiB | −0.9% / +4.1%: the plan gets worse |
| `malloc_trim(0)` before the scan | no M change; T within noise |
| Workers format the answer lines after a barrier instead of 12 new threads | output phase 2.4 → 3.2 ms (slower) |
| Static linking (`-Ctarget-feature=+crt-static`) | spawn to `main` 1.14 → 1.10 ms, exit 1.40 → 1.32 ms |
| Counting sort instead of sorting the BOOL terms by frequency | the sort is 0.6% of the serial part |
| Branch-free two-slot probe in the scan | 92.4% of lookups already hit their home slot (73.0% terms, 19.4% filter misses to the empty slot), 4.2% the next slot |

## Correctness

`experiments/b-speed4/vmtest.sh` on the PGO and plain builds: generated tiny seeds 2, 17, 99 and 4242 and sample seeds 3 and 13 at 1, 2, 7, 12 and 16 threads, the edge fixtures from 1 to 100,000 documents, and the team's fuzz, boundary, shards, randomized and edge suites at 1, 4 and 12 threads all match the official reference. As in production, only the empty `docs.txt` fixture and `b-bounded-duplicates.py` fail. A native macOS ARM build compiles without warnings and passes the fuzz, boundary, shards, randomized and edge suites. Every timed run matched the seed 1 and seed 2 hashes.

## Reproduce

Same setup as `experiments/b-speed4/README.md`:

```sh
cp experiments/b-speed5/baseline.rs ~/kiro-b/src-base.rs; cp experiments/b-speed5/candidate.rs ~/kiro-b/src-cand.rs
bash experiments/b-speed4/vm-build.sh base cand
python3 experiments/b-speed4/bench.py -n 30 -s 1,2 base-pgo cand-pgo
python3 experiments/b-speed4/tl.py experiments/b-speed5/candidate.rs ~/kiro-b/src-cand-tl.rs   # then build cand-tl
python3 experiments/b-speed4/tlrun.py -n 7 cand-tl-pgo       # phase timeline
python3 experiments/b-speed5/tlmain.py cand-tl-pgo 9         # main-thread time, CPU and faults per step
```
