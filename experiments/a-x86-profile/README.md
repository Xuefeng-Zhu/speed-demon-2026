# Track A x86 profile: CPU split, page faults, phases, memory, mmap vs pread

`baseline.rs` is the exact production `track-a/src/main.rs`, SHA-256 `269f682321dfaeeb3afb08ae1df68f8cfdf22adc261aa7b7eafb07e52fd746f0`. `profile.rs` adds only instrumentation (getrusage, `clock_gettime` CPU clocks, `/proc/self/status` and `smaps_rollup` reads, an optional RSS sampler thread, and stderr `key=value` lines); the algorithm is unchanged. `io-probe.rs` is a parse-free probe of the I/O and page-fault floor. `run.py` builds all three, runs them and writes `report.json` with every raw sample.

These are local diagnostic measurements, not official scores and not cgroup memory. Every one of the 2 x 3 warmups, 63 measured solution runs (7 baseline, 7 profile and 3 sampled profile runs at each of 6, 8 and 12 threads) produced the published output SHA-256 `495ca09682b9673ef836a506496177680bb4a3af54255174befddb1f83481cd3`. All io-probe summing modes produced identical checksums per thread count.

## Host and caveats

- Shared KVM VM, Intel Xeon Platinum 8488C, 8 vCPUs as 4 cores x 2 hyperthreads, L2 2 MiB per core, kernel 6.1.188 (amzn2023), rustc 1.92.0, Python 3.11.15. This is not the i5-13500 scoring box (6P+6E cores, 12 threads, no AVX-512).
- Input and output both live on tmpfs (`/tmp`). Because the input is on tmpfs here, its mapped pages show up as `RssShmem`, not `RssFile`; on a disk-backed `/data` they would be `RssFile`.
- No perf, strace or valgrind (perf_event_paranoid=2, not installed). The cgroup has no memory controller, so cgroup peak is only approximated from `/proc` values plus the tmpfs output size.
- getrusage `utime`/`stime` are tick-sampled on this kernel (4 ms granularity), so per-thread and per-phase user/sys splits are noisy; means over runs are given for them. Exact on-CPU time comes from `CLOCK_THREAD_CPUTIME_ID` / `CLOCK_PROCESS_CPUTIME_ID` (`cpu` fields), which do not split user from sys.
- `wait4` `ru_maxrss` includes the forked Python driver's RSS before exec (about 23 MB), so for small processes use `VmHWM` read inside the process instead.
- 12 threads oversubscribe the 8 vCPUs. Instrumentation adds roughly 0.1 to 0.8 ms of wall time (profile vs baseline medians below). Timings are medians of 7 interleaved runs after one warmup per binary and thread count.

## Reproduce

```sh
python3 experiments/a-x86-profile/run.py --data /tmp/a-full --runs 7 --threads 6,8,12
```

`run.py` generates `/tmp/a-full` with `official/generators/a_ingest.py --seed 1 --scale full` if it is missing, builds into the gitignored `experiments/a-x86-profile/target/` with `rustc --edition 2021 -C opt-level=3 -C codegen-units=1 -C lto=fat -C panic=abort -C target-cpu=x86-64-v3`, writes output to `/tmp/a-x86-out`, and writes `report.json` (raw runs under `runs`, `warmup`, `probe`; medians, means, min and max under `summary`). A single instrumented run: `SD_PROFILE_SAMPLE_US=200 SD_DATA=/tmp/a-full SD_OUT=/tmp/out experiments/a-x86-profile/target/profile`.

## 1. Process CPU time and wall time

| Threads | Baseline wall median | Profile wall median | Process CPU (exact, profile) | utime mean (baseline) | stime mean (baseline) | sys share |
|---:|---:|---:|---:|---:|---:|---:|
| 6 | 42.3 ms | 42.6 ms | 212.2 ms | 187.6 ms | 29.1 ms | 13.4% |
| 8 | 36.6 ms | 37.4 ms | 244.0 ms | 217.7 ms | 25.4 ms | 10.4% |
| 12 | 45.5 ms | 45.6 ms | 275.4 ms | 243.1 ms | 33.2 ms | 12.0% |

Baseline wall at 8 threads ranged 35.1 to 37.9 ms. Majflt was 0 in every run. Process minflt medians (baseline): 8,092 (6 threads), 8,621 (8), 9,910 (12).

## 2. Page faults and madvise

| Threads | Parse-thread minflt total | Per thread | Per MiB of input | madvise wall, slowest thread | madvise CPU, sum of threads |
|---:|---:|---:|---:|---:|---:|
| 6 | 7,001 | 1,167 | 30.7 | 0.68 ms | 3.42 ms |
| 8 | 7,053 | 882 | 31.0 | 0.55 ms | 3.26 ms |
| 12 | 7,139 | 595 | 31.3 | 0.46 ms | 3.48 ms |

The io-probe shows the file mapping alone costs about 3,649 faults (16 per MiB: kernel fault-around maps 16 pages, 64 KiB, per fault), so the remaining roughly 3,400 parse faults are anonymous record pages (about 13.9 MB at 4 KiB, matching `RssAnon`). Touching every page of the mapping (`mmap-touch`, 8 threads) costs 9.15 ms of thread CPU in total and 2.74 ms wall on the slowest thread; adding madvise gives roughly 12.4 ms CPU, about 6.8% of the 183 ms parse-thread CPU, and about 3.3 ms of a 26 ms parse thread. Summary workers add 1,351 faults (8 threads) for `lat` and output buffers.

## 3. Phase timings

Cumulative medians from main start (8 threads): mapped 0.06 ms, parse done 27.68 ms, merge done 27.93 ms, first hour written 29.45 ms, last summarize returned 35.84 ms, main done 35.91 ms. Process startup plus exit outside `main` adds 1.55 ms to the driver's wall time.

| Threads | Map + cuts | Parse | Merge/rank | Summary + write | Merge done to first written | Internal total |
|---:|---:|---:|---:|---:|---:|---:|
| 6 | 0.13 ms | 32.39 ms (78.9%) | 0.26 ms (0.6%) | 8.09 ms (19.7%) | 1.47 ms | 41.06 ms |
| 8 | 0.14 ms | 27.54 ms (76.7%) | 0.25 ms (0.7%) | 8.05 ms (22.4%) | 1.56 ms | 35.91 ms |
| 12 | 0.15 ms | 33.16 ms (75.5%) | 0.27 ms (0.6%) | 10.65 ms (24.2%) | 2.33 ms | 43.95 ms |

Parse CPU at 8 threads is 188 ms of 244 ms process CPU (77%); summary + write CPU is 55 ms. Sum of `write_all` time on the main thread is 3.1 ms for 10,113,024 bytes and overlaps summarizing. Merge done to first hour received is 0.89 ms; the rest of the gap is the first write. Parse threads are imbalanced at 6 threads (slowest 31.4 ms, fastest 19.8 ms, end spread 11.6 ms), consistent with some threads sharing a core's hyperthreads; at 8 threads the end spread is 2.3 ms.

Versus the earlier ARM profile (parse about 65%, merge about 3%, summary + write about 30%, about 4.5 ms merge to first written): on this x86 host parse is a larger share (77%), merge is now negligible (0.7%, the sharded shared maps removed the merge pass), summary + write is 22%, and the gap is 1.6 ms. The ARM profile measured an older source at 12 workers on a different machine, so this is a qualitative comparison only.

## 4. Memory composition

Medians at 8 threads, in MB (1 MB = 1,000,000 bytes for byte counts; `/proc` values are KiB converted).

| Item | Value |
|---|---:|
| VmHWM (includes the mapped input) | 240.1 MB (234,516 KiB) |
| Input pages mapped at peak (sampler total max minus anon and file) | about 220 MB, peak near 24.5 ms |
| RssAnon at parse done / first written / done | 14.2 / 14.6 / 4.6 MB |
| RssAnon sampled max (200 us sampler) | 15.2 MB at about 30 ms |
| RssFile (binary and libraries) | 2.3 MB |
| Records payload, 3,100,000 x 4 B | 12.4 MB |
| Records capacity reserved (`reserve(1 << 15)` per hour bucket) | 19.1 MB virtual; 6.7 MB of it is never touched |
| Escapes (about 38,500 x 8 B) capacity | 0.42 MB |
| Summary `lat` scratch, sum over workers | 3.4 MB capacity |
| Pending output buffers, max held | 11 hours, 2.9 MB capacity (about 148 KB used each) |
| Endpoint names (1,842) / rank table | 61 KB / 8 KB |
| Output file on tmpfs | 10.1 MB (10,113,024 bytes) |

Approximate cgroup peak if input page cache is not charged (as the earlier roughly 22 MB ARM cgroup observation implies): anon peak plus written tmpfs output plus binary pages. At first written that is 14.6 + 0.1 + 2.3 MB; at done 4.6 + 10.1 + 2.3 = 17.0 MB; an upper bound is anon max + full output + file = 15.2 + 10.1 + 2.3 = 27.6 MB, before kernel overhead (page tables, stacks). If the input page cache were charged to the cgroup, the peak would instead be dominated by about 220 to 239 MB of input pages. Thread count changes anon only slightly (RssAnon at parse done 14.0 MB at 6 threads, 14.6 MB at 12).

## 5. io-probe: mmap vs pread (no parsing)

Medians of 7 rotated runs per mode, 8 threads. `read` is the in-process wall from after mapping to all threads joined; `CPU` is the sum of exact per-thread CPU over the read loop; `HWM` is VmHWM.

| Mode | Map | Read wall | Thread CPU | madvise CPU | minflt | HWM |
|---|---:|---:|---:|---:|---:|---:|
| mmap-touch (one u64 per page, MADV_DONTNEED) | 0.01 ms | 3.21 ms | 9.15 ms | 3.96 ms | 3,756 | 197.4 MB |
| mmap-sum (all words, MADV_DONTNEED) | 0.01 ms | 6.51 ms | 37.32 ms | 4.10 ms | 3,753 | 203.9 MB |
| mmap-nodontneed-touch | 0.01 ms | 1.84 ms | 9.33 ms | 0 | 3,749 | 241.1 MB |
| mmap-nodontneed-sum | 0.01 ms | 5.76 ms | 37.18 ms | 0 | 3,751 | 241.1 MB |
| mmap-populate-sum | 4.24 ms (serial) | 5.38 ms | 31.03 ms | 4.16 ms | 3,756 | 239.8 MB |
| pread 64 KiB buffer | 0 | 6.48 ms | 43.44 ms | 0 | 233 | 1.1 MB |
| pread 256 KiB buffer | 0 | 7.04 ms | 44.39 ms | 0 | 626 | 2.5 MB |
| pread 1 MiB buffer | 0 | 8.78 ms | 63.89 ms | 0 | 2,162 | 6.9 MB |

At 6 threads, read wall was 7.75 ms mmap-sum vs 7.94 / 8.11 / 11.13 ms pread 64 KiB / 256 KiB / 1 MiB; at 12 threads 8.00 ms vs 7.48 / 8.38 / 12.02 ms. The no-madvise variants show higher HWM in the process at exit, and the driver-observed process wall was 5.2 to 5.9 ms for nodontneed vs 4.0 to 4.5 ms for mmap-touch with madvise, because the exit then unmaps all pages on one thread. Larger pread buffers get slower and fault more, since 1 MiB buffers on two hyperthreads exceed the shared 2 MiB L2.

## 6. Signal

Page faults and system time are not the bottleneck. Process sys time is 10 to 13% (tick-sampled), and the measured file-fault plus madvise cost is about 12.4 ms of 244 ms CPU at 8 threads (5%), about 3.3 ms of a 26 ms parse thread. Chunked pread does not recover it: its copy costs about as much as the faults it avoids (64 KiB pread 43.4 ms thread CPU vs mmap-sum plus madvise 41.4 ms; read wall 6.48 vs 6.51 ms at 8 threads, a difference inside run-to-run noise), larger buffers are slower, and MAP_POPULATE adds 4.2 ms of serial work. Parsing user time dominates: parse is 77% of wall and of CPU, and the parse threads spend about 183 ms of CPU against a memory-read floor of about 37 to 41 ms, so roughly 140 ms is the per-line work (field scanning, hashing and the endpoint table probe/compare, record pushes). Replacing mmap with pread is not justified for speed on this evidence. Its only plausible benefit is memory, cutting mapped input pages from about 230 MB to about 1 MB, which matters only if the scoring cgroup is charged for the input page cache; the earlier roughly 22 MB ARM cgroup observation suggests it is not.
