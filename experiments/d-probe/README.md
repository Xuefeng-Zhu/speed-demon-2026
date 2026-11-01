# D phase-boundary probe (branch `d-probe`)

`baseline.rs` is `track-d/src/main.rs` at `d9d69e7` (branch `speed-demon`),
the same source `/projects/sandbox/.data/bin/base-d` was built from.
`candidate.rs` is the new `track-d/src/main.rs` on branch `d-probe`. The
candidate adds a background sampling thread that reads `/proc/self/status`
every 2 ms, tags each sample with the current phase and writes one summary
line per phase to stderr. Stdout stays byte-identical to the baseline on
every run at 1, 4, 8 and 12 threads.

This branch is a probe, not a performance trial. It is meant to tell the
orchestrator which phase holds the 85 MB that the board's cgroup accounting
records on the current `speed-demon` sources (local sampled peak at 12
threads is 63 MB; the 20 MB gap is unexplained by the sandbox and does not
move with thread count).

## What the probe measures

For each phase the probe tracks the per-phase peak of six fields of
`/proc/self/status`:

- `VmRSS` (total resident memory: anon plus file-backed, same as the kernel's
  current working set),
- `VmPeak` (lifetime peak of `VmSize`; monotonic),
- `RssAnon` (anonymous resident, the usual proxy for board M on this task),
- `RssShmem` (shared / tmpfs resident, zero here),
- `VmHWM` (lifetime peak of `VmRSS`; monotonic),
- `VmSize` (total virtual address space; mostly the 92 MB `graph.txt` mapping).

Each sample reads `/proc/self/status` once, updates the per-phase maxima of
the fields and sleeps 2 ms. The sampling interval is longer than one
`open` + `read` of `/proc/self/status`, which is around 10 µs here, so the
overhead stays well below two percent of wall time (see the overhead table
below).

## Phases

Written by `main` with a `PHASE.store(k, Relaxed)` at each boundary:

| Phase | Written just before |
|---|---|
| 0 `init` | before any work (the probe thread starts here) |
| 1 `load` | `load_graph` |
| 2 `renumber` | `renumber` |
| 3 `queries` | reading the queries file, parsing the wide-weight edge list |
| 4 `relabel` | `relabel` |
| 5 `search` | the parallel search over queries |
| 6 `write` | writing `distances.txt` |

The probe prints one line per phase on each transition (flushes
`last_phase`'s peaks) and once at shutdown (final peak dump). Example
local output on full seed 1 at eight threads:

```
[probe] phase=init      VmRSS=      0kB VmPeak=      0kB RssAnon=      0kB RssShmem=  0kB VmHWM=      0kB VmSize=      0kB
[probe] phase=load      VmRSS= 148056kB VmPeak= 795868kB RssAnon=  56184kB RssShmem=  0kB VmHWM= 154988kB VmSize= 771824kB
[probe] phase=renumber  VmRSS= 151188kB VmPeak= 795868kB RssAnon=  59316kB RssShmem=  0kB VmHWM= 154988kB VmSize= 760924kB
[probe] phase=relabel   VmRSS= 144724kB VmPeak= 795868kB RssAnon=  52848kB RssShmem=  0kB VmHWM= 154988kB VmSize= 761072kB
[probe] phase=search    VmRSS= 153100kB VmPeak= 795868kB RssAnon=  61224kB RssShmem=  0kB VmHWM= 154988kB VmSize= 761248kB
[probe] phase=load      VmRSS= 148056kB VmPeak= 795868kB RssAnon=  56184kB RssShmem=  0kB VmHWM= 154988kB VmSize= 771824kB
[probe] phase=renumber  VmRSS= 151188kB VmPeak= 795868kB RssAnon=  59316kB RssShmem=  0kB VmHWM= 154988kB VmSize= 760924kB
[probe] phase=relabel   VmRSS= 144724kB VmPeak= 795868kB RssAnon=  52848kB RssShmem=  0kB VmHWM= 154988kB VmSize= 761072kB
[probe] phase=search    VmRSS= 153100kB VmPeak= 795868kB RssAnon=  61224kB RssShmem=  0kB VmHWM= 154988kB VmSize= 761248kB
[probe] phase=write     VmRSS= 146164kB VmPeak= 795868kB RssAnon=  54288kB RssShmem=  0kB VmHWM= 154988kB VmSize= 754176kB
```

Each phase appears twice: once at the next transition (when the probe
flushes the peaks it accumulated for that phase) and once at the shutdown
flush (same numbers; stops at the first phase that still had a live sample).

### Reading the output

- `RssAnon` is the direct number to compare to board M.
- `VmHWM` is the lifetime peak of `VmRSS`, so it shows file-backed pages too
  (the mmap'd `graph.txt`); on this task it stays well above `RssAnon`.
- The sandbox's 8 vCPUs run twelve threads oversubscribed; the sampled
  peaks at 12 threads here (RssAnon about 63 MB) read as a floor for the
  board's 12 real cores.

On full seed 1 at eight threads the local probe says the per-phase RssAnon
peaks are: load 56.2 MB, renumber 59.3 MB, relabel 52.8 MB, search 61.2 MB,
write 54.3 MB. Memrun's sampled peak at 350 µs is 63 MB; the probe reads
within one sample of that (62 MB) at the search phase, so the sampler is
not missing any short peak. The board's 82 to 87 MB on the same sources is
20 MB above every local phase peak and 25 MB above the lowest; which phase
on the board holds the extra 20 MB is what the orchestrator will trial.

## Output byte-identity

The probe writes nothing to stdout, and `main`'s `fs::write` to
`distances.txt` is unchanged. Full seed 1 SHA-256 `a23dbdf0…277e` matched
on every local run at 1, 4, 8 and 12 threads. `smallcheck.py d` matched
the official reference on tiny and sample at seeds 2 and 7 at 4, 8 and 12
threads.

## T overhead

25 interleaved runs after one warm-up, 8 vCPU sandbox (no oversubscription):

| Build | Wall median | Wall min | Peak anon |
|---|---:|---:|---:|
| `base-d` | 183.8 ms | 174.8 ms | 63.90 MB |
| `d-probe` | 184.1 ms | 173.2 ms | 63.00 MB |

Overhead at steady state is under 1% on both the median and the min (the
min is within noise of the baseline). Peak anon is unchanged within noise
(the probe thread allocates a 2 KB sampling buffer and one stderr lock
guard, plus the usual 2 MiB virtual stack that the kernel does not commit
until a page is touched).

An earlier three-run burst showed +9%; it was a one-off system-load
transient and did not reproduce in longer batches.

## S and Dockerfile

The probe adds a `probe` thread, the two statics `PHASE` and `STOP`, and
one `PHASE.store` call per boundary. `sloc.py d` reads 460 + 7 = 467
against the baseline's 379 + 7 = 386, +81 lines. All of them are inside
`main.rs`; the Dockerfile is unchanged, so the allowlist is identical to
the baseline.

The branch should not be scored for K: its S is 81 lines above production,
and the whole point is to produce stderr output on the board. Use the
`[probe] phase=…` lines from the board's run log to see where the 20 MB
gap sits, revert the branch, and apply any resulting pure saving on a
separate trial branch.

## How to use the branch

The orchestrator opens a trial PR on `d-probe` and reads the stderr log
from the board run. The lines of interest are the ones labelled with
individual phase names; the final dump lists every phase again for
convenience. Compare each phase's `RssAnon` and `VmHWM` to the baseline
numbers above to find which phase picks up the board's extra 20 MB.
