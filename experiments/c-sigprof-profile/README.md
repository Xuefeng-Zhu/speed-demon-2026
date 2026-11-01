# Track C line-level CPU profile (SIGPROF sampler)

The sandbox VM has no `perf`. The root filesystem is read-only, the package mirror is blocked, and the KVM guest exposes no hardware PMU, so `perf_event_open` fails for every hardware event. Instead, `prof.rs` gives each worker a per-thread CPU-time timer (`timer_create(CLOCK_THREAD_CPUTIME_ID)` with `SIGEV_THREAD_ID`) that fires every 200 µs. A `SIGPROF` handler records the interrupted instruction address. `symbolize.py` runs the profiling binary several times, maps each address through `/proc/self/maps` and `addr2line -i` (inlined frames included) or libc's symbol table, and groups samples by main.rs line and by stage.

Samples are CPU time only, not wall time or stall cause: there are no cache-miss or branch counters. Kernel time lands on the user instruction where the thread returns, for example the `syscall` wrapper for a futex wait. Main-thread work outside the workers is not sampled.

## Results (full seed 1, sandbox AMD EPYC 7R13, 8 vCPUs)

`report-171ca6f-8t.txt` profiles the Track C source at `171ca6f` (owner routing, 16 chunks) on 8 threads, 25 runs, 458 ms CPU per run:

- **9.1% in libc `syscall`**: futex waits. `mark` took the owner's inbox lock in a `for` header, `for v in std::mem::take(&mut *inbox[t].lock().unwrap())`. Rust drops a temporary in a `for` header only after the loop ends, so the lock was held while the owner processed every queued block. Each worker spent 6.5–9.2 ms of its 50–57 ms in `mark`, and producers that pushed a full block meanwhile blocked in the futex.
- Dictionary probe (`Names::id`) 13.0%; owner bitset marking 10.8%; record field and number parsing about 18%; name hash 6.6%; AVX2 masks 6.6%; routing pushes 5.0%; `madvise` 2.6%.

`report-unlock-8t.txt` is the same source with the lock released before the loop (one line): futex time falls to 2.7%, and CPU per run from 458 to 434 ms. In interleaved 8-thread wall-time batches (30 rounds each, trimmed means, both orders) it measured 57.8 / 57.9 ms against 59.6 / 60.1 ms for `171ca6f` (about −3.5%). Anonymous RSS is unchanged at 7.4 MB.

`report-unlock-1t.txt` is the fixed source on one thread. With no contention, the probe falls to 4.3% while parsing (record fields plus `ld`/`num`) is about 30%. At 8 threads the probe is 13.6%. That gap points to cross-core traffic on the shared slot table during inserts and reads, rather than probe instructions.

Rejected in the same session (8 threads, trimmed means against the lock fix at 56.8–57.8 ms): moving the insert CAS after the `used` check and dropping the extra `fetch_add` condition, 58.0; prefetching `seen_in` lines 16 events ahead in `mark`, 57.6; 4,096-event blocks, 56.9; reusing emptied blocks instead of allocating, 59.0–59.7.

## Reproduce

```sh
# copy track-c, add the prof module as described at the top of prof.rs, then:
CATS='[[first_line,last_line,"stage name"], ...]' python3 symbolize.py path/to/profiling-binary 25 0-7
```

`CATS` maps main.rs line ranges of the profiling copy to stage names; without it only the line and libc tables are printed.
