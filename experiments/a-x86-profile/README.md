# Track A x86 profile: CPU split, page faults, phases, memory, mmap vs pread

`baseline.rs` is the exact production `track-a/src/main.rs`, SHA-256 `269f682321dfaeeb3afb08ae1df68f8cfdf22adc261aa7b7eafb07e52fd746f0`. `profile.rs` adds only instrumentation (getrusage, `clock_gettime` CPU clocks, `/proc/self/status` and `smaps_rollup` reads, an optional RSS sampler thread, per-hour summarize timings, writer head-of-line timings, and stderr `key=value` lines); the algorithm is unchanged. `io-probe.rs` is a parse-free probe of the I/O and page-fault floor. `run.py` builds all three, runs them and writes `report.json` with every raw sample.

These are local diagnostic measurements, not official scores and not cgroup memory. Every one of the 6 warmups (one baseline and one profile per thread count) and 51 measured solution runs (7 baseline, 7 profile and 3 sampled profile runs at each of 6, 8 and 12 threads) produced the published output SHA-256 `495ca09682b9673ef836a506496177680bb4a3af54255174befddb1f83481cd3`. All io-probe summing modes produced identical checksums per thread count.

## Host and caveats

- Shared KVM VM, Intel Xeon Platinum 8488C, 8 vCPUs as 4 cores x 2 hyperthreads, L2 2 MiB per core, kernel 6.1.188 (amzn2023), rustc 1.92.0, Python 3.11.15. This is not the i5-13500 scoring box (6P+6E cores, 12 threads, no AVX-512).
- Input and output both live on tmpfs (`/tmp`). Because the input is on tmpfs here, its mapped pages show up as `RssShmem`, not `RssFile`; on a disk-backed `/data` they would be `RssFile`.
- No perf, strace or valgrind (perf_event_paranoid=2, not installed). The cgroup has no memory controller, so cgroup peak is only approximated from `/proc` values plus the tmpfs output size.
- getrusage `utime`/`stime` are tick-sampled on this kernel (4 ms granularity), so per-thread and per-phase user/sys splits are noisy; per-run process `stime` ranges from 0 to 74 ms. Means over runs are given for them. Exact on-CPU time comes from `CLOCK_THREAD_CPUTIME_ID` / `CLOCK_PROCESS_CPUTIME_ID` (`cpu` fields), which do not split user from sys.
- `wait4` `ru_maxrss` includes the forked Python driver's RSS before exec (about 23 MB), so for small processes use `VmHWM` read inside the process instead.
- 12 threads oversubscribe the 8 vCPUs. Instrumentation (including one stderr line per summarized hour) adds roughly 0.6 to 1.2 ms of wall time (profile vs baseline medians below). Timings are medians of 7 interleaved runs after one warmup per binary and thread count.

## Reproduce

```sh
python3 experiments/a-x86-profile/run.py --data /tmp/a-full --runs 7 --threads 6,8,12
```

`run.py` generates `/tmp/a-full` with `official/generators/a_ingest.py --seed 1 --scale full` if it is missing, builds into the gitignored `experiments/a-x86-profile/target/` with `rustc --edition 2021 -C opt-level=3 -C codegen-units=1 -C lto=fat -C panic=abort -C target-cpu=x86-64-v3`, writes output to `/tmp/a-x86-out`, and writes `report.json` (raw runs under `runs`, `warmup`, `probe`; medians, means, min and max under `summary`). A single instrumented run: `SD_PROFILE_SAMPLE_US=200 SD_DATA=/tmp/a-full SD_OUT=/tmp/out experiments/a-x86-profile/target/profile`.

Instrumentation-only check: `diff experiments/a-x86-profile/baseline.rs experiments/a-x86-profile/profile.rs | grep '^<'` lists every baseline line that `profile.rs` changes. It prints exactly two: the summary worker loop `for _ in 0..threads.min(HOURS)` (renamed to `for w in ...` so the worker index can be logged) and `tx.send((h, summarize(...)))` (split into `let out = summarize(...)`, timing and `hour_job` logging, then `tx.send((h, out))`). Every other difference is an added line. The `hour_job` line is printed before each hour is sent, which delays its receipt by a few microseconds, negligible against the 0.55 ms hour-0 wait below.

## 1. Process CPU time and wall time

| Threads | Baseline wall median | Profile wall median | Process CPU (exact, profile) | utime mean (baseline) | stime mean (baseline) | sys share (baseline) | sys share (baseline + profile, 14 runs) |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 6 | 42.6 ms | 43.2 ms | 213.5 ms | 195.2 ms | 20.5 ms | 9.5% | 12.1% |
| 8 | 36.3 ms | 37.0 ms | 244.0 ms | 200.2 ms | 43.6 ms | 17.9% | 14.8% |
| 12 | 44.8 ms | 46.0 ms | 277.2 ms | 225.8 ms | 49.8 ms | 18.1% | 16.6% |

Baseline wall at 8 threads ranged 34.8 to 38.1 ms. Majflt was 0 in every run. Process minflt medians (baseline): 8,128 (6 threads), 8,653 (8), 9,690 (12). Because of the 4 ms tick sampling, the sys share moves by several points between reruns (an earlier run of this same script gave 10 to 13%); read it as roughly 10 to 18%, not as a precise figure.

## 2. Page faults and madvise

| Threads | Parse-thread minflt total | Per thread | Per MiB of input | madvise wall, slowest thread | madvise CPU, sum of threads |
|---:|---:|---:|---:|---:|---:|
| 6 | 7,003 | 1,167 | 30.7 | 0.80 ms | 3.61 ms |
| 8 | 7,049 | 881 | 30.9 | 0.61 ms | 3.67 ms |
| 12 | 7,135 | 595 | 31.3 | 0.51 ms | 3.81 ms |

The io-probe shows the file mapping alone costs about 3,649 faults (16 per MiB: kernel fault-around maps 16 pages, 64 KiB, per fault), so the remaining roughly 3,400 parse faults are anonymous record pages (about 13.9 MB at 4 KiB, matching `RssAnon`). Two estimates of the in-thread file-fault cost at 8 threads:

- Upper bound: `mmap-touch` thread CPU, 9.54 ms. Touch mode reads one byte per page, so each read is also a cold cache line and TLB miss, and this figure includes that memory latency.
- Closer estimate: `mmap-sum` minus `mmap-populate-sum` thread CPU, 37.37 - 29.60 = 7.77 ms (MAP_POPULATE moves the faults out of the threads into 4.40 ms of serial work at map time).

Adding the parse threads' own madvise CPU (3.67 ms) gives 11.4 to 13.2 ms of CPU, 6.2 to 7.2% of the 182.9 ms parse-thread CPU (sum of per-thread clocks) and 4.7 to 5.4% of the 244 ms process CPU. Per thread that is at most about 2.2 ms (touch slowest thread 1.61 ms plus madvise 0.61 ms) of a 25.7 ms parse thread. Summary workers add 1,405 faults (8 threads) for `lat` and output buffers.

## 3. Phase timings

Cumulative medians from main start (8 threads): mapped 0.06 ms, parse done 26.81 ms, merge done 27.05 ms, first hour written 28.62 ms, last summarize returned 35.33 ms, main done 35.45 ms. Process startup plus exit outside `main` adds 1.52 ms to the driver's wall time.

| Threads | Map + cuts | Parse | Merge/rank | Summary + write | Merge done to first written | Internal total |
|---:|---:|---:|---:|---:|---:|---:|
| 6 | 0.13 ms | 32.89 ms (78.7%) | 0.26 ms (0.6%) | 8.37 ms (20.0%) | 1.40 ms | 41.76 ms |
| 8 | 0.13 ms | 26.68 ms (75.3%) | 0.25 ms (0.7%) | 8.33 ms (23.5%) | 1.52 ms | 35.45 ms |
| 12 | 0.15 ms | 32.82 ms (74.1%) | 0.27 ms (0.6%) | 11.00 ms (24.9%) | 2.63 ms | 44.26 ms |

Two parse CPU figures are used in this README. The process CPU clock across the parse phase (`cuts` to `parse_done`) is 188.0 ms of 244 ms process CPU at 8 threads (77%); it also counts the main thread and thread spawn/join. The sum of the parse threads' own CPU clocks is 182.9 ms; sections 2 and 6 use this one. Summary + write CPU (process clock) is 55.2 ms. Sum of `write_all` time on the main thread is 3.13 ms for 10,113,024 bytes in 72 writes and overlaps summarizing. Parse threads are imbalanced at 6 threads (slowest 31.7 ms, fastest 20.2 ms, end spread 11.5 ms), consistent with some threads sharing a core's hyperthreads; at 8 threads the end spread is 1.9 ms.

### Merge done to first written: head-of-line wait for hour 0

The writer must emit hours in order, so it holds every hour that arrives before hour 0. `profile.rs` records the first hour received, the hour-0 receive time, the hours held at that point, the duration of hour 0's `write_all`, and every hour's summarize start, duration and record count (`hour_job` lines). Medians:

| Threads | Merge done to first receipt | First hour received (range) | Hours held when hour 0 arrives | First receipt to hour 0 received | Hour 0 `write_all` | Hour 0 summarize | Other first-wave hours summarize | Hour 0 records vs other first-wave hours |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 6 | 1.07 ms | 5 (0 to 5) | 5 | 0.26 ms | 0.054 ms | 1.18 ms | 0.93 ms | 69,549 vs 49,811 |
| 8 | 0.92 ms | 7 (7 to 7) | 9 | 0.55 ms | 0.055 ms | 1.31 ms | 0.95 ms | 69,549 vs 39,594 |
| 12 | 1.58 ms | 10 (7 to 11) | 10 | 0.99 ms | 0.054 ms | 2.30 ms | 1.81 ms | 69,549 vs 22,284 |

At 8 threads the 1.52 ms gap is 0.92 ms until the first hour comes back (worker spawn plus one smaller hour's summarize; hour 0 starts 0.12 ms after merge done), 0.55 ms of waiting for hour 0 itself while later hours queue up, and 0.055 ms for hour 0's write. Records fall steadily across the first wave (hour 0 69,549, hour 1 64,963, down to hour 7 18,861 at 8 threads), so hour 0 is the largest first-wave hour and finishes last in that wave. It is not the largest hour overall: hour 46 has 73,244 records and hour 0 ranks 10th of 72. Hour 0 has 1.6x the median hour (43,537) and 1.8x the other first-wave hours. The write is not the cost.

This wait is not on the wall-time critical path. `write_all` costs about 43 us per hour, far less than a summarize, so once hour 0 lands the writer drains the held hours and keeps up. The process ends shortly after the last summarize returns: `t_done - t_summary_done` has a median of 0.12 ms at 6 threads (0.05 to 0.16 ms), 0.20 ms at 8 (0.05 to 0.28 ms) and 0.47 ms at 12 (0.15 to 0.92 ms). Wall time is set by when the summary workers finish, not by when hour 0 is written. The only cost of the wait is memory: output buffers for hours that arrive before hour 0 stay in anon memory longer, up to 11 held hours (2.9 MB capacity) at 8 threads, 6 (1.6 MB) at 6 and 21 (5.5 MB) at 12. Hour 0 is already dispatched first at every thread count, so a largest-first dispatch order would not shorten this gap (it would put hour 46 and other larger hours ahead of hour 0 and make it longer). Splitting hour 0 into smaller jobs would move the first write earlier and lower the held peak, but would not change `t_done` unless it also rebalanced the summarize tail, which this experiment does not measure.

Versus the earlier ARM profile (parse about 65%, merge about 3%, summary + write about 30%, about 4.5 ms merge to first written): on this x86 host parse is a larger share (75%), merge is now negligible (0.7%, the sharded shared maps removed the merge pass), summary + write is 24%, and the gap is 1.5 ms. The ARM profile measured an older source at 12 workers on a different machine, so this is a qualitative comparison only.

## 4. Memory composition

Medians at 8 threads, in MB (1 MB = 1,000,000 bytes; `/proc` KiB values are converted).

| Item | Value |
|---|---:|
| VmHWM (includes the mapped input) | 239.9 MB (234,232 KiB) |
| Input pages mapped at peak (sampler total max minus anon and file) | about 220 MB, peak near 24.2 ms |
| RssAnon at parse done / first written / done | 14.2 / 14.6 / 4.7 MB |
| RssAnon sampled max (200 us sampler) | 15.0 MB at about 29.8 ms |
| RssFile (binary and libraries) at parse done | 2.3 MB (2,248 KiB) |
| Records payload, 3,100,000 x 4 B | 12.4 MB |
| Records capacity reserved (`reserve(1 << 15)` per hour bucket) | 19.1 MB virtual; 6.7 MB of it is never touched |
| Escapes (about 38,800 x 8 B) capacity | 0.42 MB |
| Summary `lat` scratch, sum over workers | 3.6 MB capacity |
| Pending output buffers, max held | 11 hours, 2.9 MB capacity |
| Endpoint names (1,842) / rank table | 61 KB / 8 KB |
| Output file on tmpfs | 10.1 MB (10,113,024 bytes) |

VmHWM depends strongly on thread count, because it is set by how many chunks' input pages are mapped at once before each thread's madvise: medians 186.0 MB (181,596 KiB) at 6 threads, 239.9 MB at 8 and 199.9 MB (195,244 KiB) at 12, with per-run ranges of 178,468 to 219,136 KiB, 229,716 to 238,852 KiB and 177,260 to 204,348 KiB. Do not read the 8-thread value as a constant. Anon memory barely moves with thread count (RssAnon at parse done 14.0 MB at 6 threads, 14.6 MB at 12).

Approximate cgroup peak if input page cache is not charged: anon peak plus written tmpfs output plus binary pages. At first written that is 14.6 + 0.1 + 2.3 = 17.0 MB; at done 4.7 + 10.1 + 2.3 = 17.1 MB; an upper bound is anon max + full output + file = 15.0 + 10.1 + 2.3 = 27.4 MB, before kernel overhead (page tables, stacks). The premise that input page cache is not charged is not measured on this host (no memory controller); it comes from the earlier roughly 22 MB ARM cgroup observation. If the input page cache were charged, the peak would instead be dominated by about 180 to 240 MB of input pages depending on thread count.

## 5. io-probe: mmap vs pread (no parsing)

Medians of 7 rotated runs per mode, 8 threads. `read` is the in-process wall from after mapping to all threads joined; `CPU` is the sum of exact per-thread CPU over the read loop; `minflt` is the process total; `HWM` is VmHWM.

| Mode | Map | Read wall | Thread CPU | madvise CPU | minflt | HWM |
|---|---:|---:|---:|---:|---:|---:|
| mmap-touch (one byte per page, MADV_DONTNEED) | 0.01 ms | 2.63 ms | 9.54 ms | 4.70 ms | 3,755 | 210.5 MB |
| mmap-sum (all words, MADV_DONTNEED) | 0.01 ms | 5.91 ms | 37.37 ms | 4.26 ms | 3,756 | 208.8 MB |
| mmap-nodontneed-touch | 0.01 ms | 1.88 ms | 9.47 ms | 0 | 3,751 | 241.1 MB |
| mmap-nodontneed-sum | 0.01 ms | 5.58 ms | 37.11 ms | 0 | 3,751 | 241.2 MB |
| mmap-populate-sum | 4.40 ms (serial) | 5.73 ms | 29.60 ms | 4.05 ms | 3,754 | 239.9 MB |
| pread 64 KiB buffer | 0 | 6.33 ms | 43.16 ms | 0 | 233 | 1.1 MB |
| pread 256 KiB buffer | 0 | 6.32 ms | 44.56 ms | 0 | 626 | 2.5 MB |
| pread 1 MiB buffer | 0 | 8.79 ms | 63.09 ms | 0 | 2,162 | 6.9 MB |

At 6 threads, read wall was 7.64 ms mmap-sum vs 7.98 / 7.92 / 10.82 ms pread 64 KiB / 256 KiB / 1 MiB; at 12 threads 8.06 ms vs 8.36 / 8.68 / 10.95 ms. The no-madvise variants show higher HWM in the process at exit, and the driver-observed process wall was 5.3 to 6.0 ms for mmap-nodontneed-touch vs 3.7 to 4.8 ms for mmap-touch with madvise across thread counts, because the exit then unmaps all pages on one thread. Larger pread buffers are slower; why is not measured here (one guess is that two 1 MiB buffers on a core's hyperthreads crowd its 2 MiB L2). Their extra faults are only the buffer's first touch (2,056 thread faults at 8 x 1 MiB, exactly 257 per thread).

This is a floor comparison only: no end-to-end pread variant of `parse` was built. Every bias of the probe favours pread. A summing loop is bandwidth-bound, so pread's extra kernel copy costs as little as it can, while under real parsing mmap's page reads can overlap with compute through hardware prefetch and pread's copy is a serialized syscall.

## 6. Signal

Page faults and system time are not the bottleneck. Process sys time is roughly 10 to 18% (tick-sampled, noisy), and the measured in-thread file-fault plus madvise cost at 8 threads is 11.4 to 13.2 ms of CPU (the larger figure is an upper bound that includes per-page memory latency), 4.7 to 5.4% of 244 ms process CPU and at most about 2.2 ms of a 25.7 ms parse thread. Chunked pread does not recover it: its copy costs about as much as the faults it avoids (64 KiB pread 43.16 ms thread CPU vs mmap-sum plus madvise 41.63 ms; read wall 6.33 vs 5.91 ms at 8 threads), larger buffers are slower, and MAP_POPULATE adds 4.4 ms of serial work. Parsing user time dominates: parse is 75% of wall and 77% of process CPU, and the parse threads spend 182.9 ms of CPU (sum of thread clocks) against a memory-read floor of about 37 to 42 ms, so roughly 140 ms is the per-line work (field scanning, hashing and the endpoint table probe/compare, record pushes). Replacing mmap with pread is not justified for speed on this evidence, and since the probe favours pread, an end-to-end variant is unlikely to change that. Its only plausible benefit is memory, cutting mapped input pages from about 180 to 240 MB to about 1 MB, which matters only if the scoring cgroup is charged for the input page cache; the earlier roughly 22 MB ARM cgroup observation suggests it is not, but this host cannot confirm it. The gap decomposition is not a speed lever: about 0.55 ms at 8 threads is the writer waiting for hour 0, the largest first-wave hour (hour 46 is larger overall), but that wait is off the wall-time critical path because the process ends 0.2 ms (median) after the last summarize returns. Its only effect is holding up to 11 finished hours (2.9 MB of output capacity) in anon memory a little longer, a small memory effect, not a wall-time saving.
