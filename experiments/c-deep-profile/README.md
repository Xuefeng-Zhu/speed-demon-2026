# Track C: why is the board twice as slow as first place?

All timings below are from the 8-vCPU sandbox (AMD EPYC 7R13, 4 cores × 2 SMT, full seed 1). They are not board numbers. "8 threads" means `taskset -c 0-7`, and A/B results are trimmed means of 30 interleaved rounds. The source under study is `e4308ed` (owner routing by group, `pread`, 16 chunks, inbox unlock), board T = 45.9 ms.

## 1. The board loses more than the sandbox predicts

On the sandbox the program scales with cores:

| CPUs | 1 | 2 cores | 4 cores | 4 cores × SMT |
|---|---:|---:|---:|---:|
| median wall | 217 ms | 119 ms | 70 ms | 56 ms |

The scoring box has 6 P-cores at a higher clock (cpuset 0–11, per the harness README). With this scaling it should land near 25–30 ms, yet it measures 45.9 ms. Two board results show that it penalises cross-core traffic much more than the sandbox:

- PR #8 (per-record `fetch_or` on shared lines) was faster on the sandbox but went from 48.4 to 58.1 ms on the board.
- `pread` (no per-chunk `MADV_DONTNEED` TLB shootdowns) was 2–3% faster on the sandbox but 6 ms faster on the board.

## 2. What the hot loop shares between cores

- **`Names.used`**: the insert counter, which `Names::id` also read on every probe step. It lived in the same struct as `Names.slots`, on `main`'s stack, near `next`, `cap`, `stride`, `region` and `inbox`. Every one of the ~10^5 inserts (most in the first quarter of the file) invalidated that line in every other core, and every record's probe then reloaded it from another core.
- **`next`**: the chunk counter, on the same stack, written once per chunk.
- **Inbox mutexes**: adjacent in one `Vec`, so locking one owner's inbox invalidated its neighbours' locks.
- **The shared slot table**: CAS inserts, then cross-core reads of lines that other cores wrote.
- **Event blocks** moving from producers to owners. This is bulk, sequential traffic.

## 3. Changes measured

| variant | 8 threads | change | S |
|---|---:|---:|---:|
| `e4308ed` | 56.5 ms | — | 336 |
| `used` on its own page, read only on an empty slot | 53.7 ms | −5% | |
| per-thread copies of the hot pointers only | 56.7 ms | ~0 | |
| both, plus padded inbox locks and `next` on its own page (`fs`) | 52.4 ms | −7% | 342 |
| no shared counter at all: overflow = a probe longer than 1,024 slots (`fs2`, PR) | 52.2–53.1 ms | −7% | 340 |
| events routed by name hash to owners with private dictionaries (`ob`) | 50.8–51.3 ms | −10% | 328 |

Single-thread time does not change for any of them (215–220 ms), as expected when the cost being removed is cross-core.

`ob` removes the shared dictionary entirely. A producer hashes the name and sends `hash & !0xFF | group` to owner `hash >> 32 · n >> 32`. The owner keeps a private open-addressing table of five-word slots (key plus a 256-bit group set) and counts first sightings. The total table size is the same 5.2 MB. Identity becomes 56 bits of the hash (collision probability about 7e-8 per dataset, versus 3e-10). Its owner stage is now the largest single item, 24.7% of CPU (`profile-name-owners-8t.txt`).

## 4. Where the remaining time goes

Removing stages one at a time (`ablate.py`; these builds give wrong output and only show cost):

| | 1 thread | 4 cores | 8 threads |
|---|---:|---:|---:|
| full `e4308ed` | 217 | 69.8 | 56.4 |
| − routing and marking | 183 | 57.0 | 45.2 |
| − dictionary probe | 157 | 43.8 | 32.9 |
| − name hash | 124 | 37.0 | 27.7 |

Even with all name handling removed, parsing plus aggregation takes 27.7 ms on 8 threads. A line profile of that parse-only build on one thread puts about 30% in the three SWAR number parses (`num`) and the loads that feed them. The 64-byte masks, prefix XOR and field-end loop together take about 15%.

## 5. Tried and not kept

- **A parser that needs no quote parity to find records** (`digit-lf-parser.rs`). A record ends at the first LF after a digit or CR, because names and notes hold no digits (spec 2.2). The last two commas are found from a 32-byte load before the terminator, and only the name is scanned with a quote mask. It passes every reference check, but parse-only time moved only from 124 to 119 ms on one thread, and it was slower in the full program (58.7 vs 56.3 ms).
- **In the `ob` design:** prefetching 16 events ahead instead of 8 (no change); separate key and set arrays (no change); event blocks of 256, 512 or 2,048 (256 and 512 slower, 2,048 the same); `M_TRIM_THRESHOLD` raised (no change).
- **On the current source:** 32 or 64 chunks with `pread` (within noise); 32 KiB or 16 KiB read buffers (slower).

## 6. Fixed costs

Measured inside the process on 8 threads:

| step | time |
|---|---:|
| `exec` to `main` (dynamic loading) | ~0.1 ms |
| spawning 8 threads | ~0.6 ms |
| regions table done | ~0.9–1.7 ms |
| output written after the last worker | ~0.4 ms |
| exit | ~1 ms |

At most 2–3 ms of a 46 ms board run is fixed cost.

## 7. Memory

Anonymous RSS at exit is 7.4 MB for `e4308ed` and `fs2`, and 7.6 MB for `ob` (u64 events). It breaks down as `seen_in` 3.9 MB, slots 1 MB, region table 1 MB and about 150 KB of malloc arena per thread. File-backed RSS adds 4.1 MB: `regions.csv` 2.1 MB, libc 1.4 MB and the binary 0.24 MB. The board's M is 11.8 MB.

## 8. After #23 (`d61a2e1`, board T = 41.0 ms): page faults inside the parse

Phase timestamps on a 1,000-record file (`fixed`, the first 60 KB of seed 1 full) showed each worker spending 1–3 ms in the final `mark` for only about 100 events. `getrusage(RUSAGE_THREAD)` showed 60–170 minor faults inside that call: the first touch of each owner's slots. On the full file those faults are spread over the run. Each one takes the address-space lock while other threads keep faulting and reading.

Fixes, each measured against the previous step (8 threads, 30-round interleaved trimmed means, both orders):

| step | change | 8 threads | S |
|---|---|---:|---:|
| `d61a2e1` | — | 50.3–50.5 ms | 328 |
| k1 | each owner writes one word per page of its slots before parsing | 45.6–45.8 ms | 329 |
| k2 | country flags: load before store, so threads stop writing the same lines | 45.4–45.7 ms | 330 |
| k8 | three-word name hash with no length loop; `mark` after every 64 KiB refill | 43.3–43.7 ms | 331 |

Single-thread time fell only 4% (217 → 211 ms). Worker CPU per run fell from 341 to 306 ms, and minor faults from about 3,700 to 2,300 per run. Max RSS is unchanged (11.7 MB median). The committed source measured 43.7 / 43.7 ms against 50.4 / 50.3 ms for `d61a2e1`.

Also measured and not kept:
- **Read-touching the slots instead of writing:** slower (51.4 ms). A read maps the shared zero page, and the later write faults again.
- **`MADV_POPULATE_WRITE` instead of the write loop:** the same speed.
- **Spawning threads as a binary tree:** about 0.5% faster but 14 more lines. Without draining the inbox after every refill, it also raised max RSS by 1.5 MB.
- **Claiming regions slices dynamically, with no barrier wait for the last spawned thread:** about 1% faster, 15 more lines.
- **Returning emptied event blocks to their producer:** no faster, 0.5 MB more RSS.
- **Releasing each owner's slots with `MADV_DONTNEED` before exit:** no change.
- **Ring depth 4 or 8:** no change.
- **Pinning each worker to one CPU:** no change.

`profile-prefault-8t.txt` is the line profile after k8. Owner probing and group bits take 16.8% of worker CPU, number parsing about 25%, the field-end loop 8.5%, `pread` copies 8.8% and the 64-byte scan about 9%.

A synthetic check of branch cost (all records padded to exactly 128 bytes, against random padding) was inconclusive. The randomly padded file came out 52% larger (647 MB vs 425 MB), so the two parse times (232 vs 172 ms) do not isolate the branch effect, and no conclusion is drawn from them.
