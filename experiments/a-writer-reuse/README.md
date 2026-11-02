# Track A writer and output-buffer reuse candidate

This change keeps all N parsing workers, then uses N−1 summary workers when N>1
while the main thread writes. N=1 keeps a summary worker. Fully written buffers
can be reused through a mutex-protected pool holding at most four idle buffers.
A pool miss allocates immediately. Output ordering and pending-hour scheduling
are unchanged, and no physical CPU is pinned or reserved.

The exact native-tested source is applied in `track-a/src/main.rs`. Its source
SHA-256 is `40d5644ddd993cb1692c0eeb5f75e2cf3ab8b16b28c76d42fbd8013f46718614`.
The shared-dictionary baseline has SHA-256
`d0c265b4aa458f4e00336215848115293be62e78d5a9f7d4703b4c8f35687221`.
Track A stayed byte-identical between the experiment baseline `ec8e317` and
the PR's refreshed base `c7ebe6d`.

## Measured results

Local native x86 VM, guest-reported Xeon Platinum 8573C, 8 cores / 16 logical
CPUs, Linux 7.0.0-1017-azure. The scoring machine differs; 20 workers oversubscribe
this VM. No official score improvement is established.

| Full input | Blocks per worker count | 16-worker ratio | 20-worker ratio |
|---|---:|---:|---:|
| Seed 1, cap-selection screen | 11 | 0.9355 | 0.9491 |
| Seed 2, fresh confirmation | 15 | 0.9287 | 0.9932 |
| Seed 3, fresh confirmation | 15 | 0.9445 | 0.9770 |

Ratios are candidate/baseline. Each block has five adjacent randomized A/B pairs;
its ratio compares the two independently sorted middle-three-of-five means. The
table reports the median block ratio. A/A controls use the identical executable
path. The source and candidate binary identity are stable across the three
inputs. The 16-worker result is consistent; at 20 workers, the seed-2 exploratory
interval crosses one. Raw multi-second outliers and shared-VM drift are retained;
this is evidence about central time, not tail-latency improvement.

| Workers | Baseline median / greatest peak, bytes | Candidate median / greatest peak, bytes |
|---:|---:|---:|
| 16 | 24,408,064 / 24,727,552 | 24,399,872 / 25,063,424 |
| 20 | 25,718,784 / 26,763,264 | 25,645,056 / 27,508,736 |

These are five randomized fresh native-container runs per source/worker count,
with input warmed outside the container. Greatest peaks rise 1.4% / 2.8%; median
peaks are essentially flat. They include the loader, shell/cat wrapper and
charged output pages and do not replace official parent-cgroup M. Local formatted
code lines grow from 398 to 412; official S may differ. Runtime dependencies are
unchanged. The four-entry idle pool is not a byte limit or a bound on all output
memory: buffers can grow and completed pending hours still use the original queue.

## Validation and retained evidence

The selected source passed 55 native check groups: 15 full/reference, page-end
and percentile-grid checks, 20 adversarial cases and 20 forced-hash-collision
cases. Full seed 1 was checked at `1,2,3,6,8,16,20,default`; four sample seeds
were compared with the official reference. The complete experiment study checked
11,516 timed outputs, including 664 warmups, and 60 outputs in completed memory
studies. These counts span the study's candidates, not only the selected source.

`summary.json` contains the selected candidate's controls, timing intervals,
source/binary hashes, memory peaks and complete correctness result. The archive
contains the original experiment sources, scripts, raw measurements and logs,
including rejected variants and clearly marked interrupted attempts. Its original
lab report describes the production state at collection time; this PR applies
the selected source afterward.

Check the archive manifest, all timed output hashes and the production source
identity without extracting or executing benchmark code:

```sh
python3 experiments/a-writer-reuse/verify-evidence.py
```

## Reproduce on a native VM

Extract the evidence from the repository root into the original experiment paths:

```sh
tar -xzf experiments/a-writer-reuse/evidence.tar.gz
```

The compiler/runtime tool image used for timings was:

```text
halloumee/speed-demon-rust:1.99.1-trixie-llvm-tools@sha256:13e4ee7135d8eac6c56476c7d1aee201f36479f4745fd5d0e6b4529f4e13251a
```

In a private copy on an otherwise idle native x86 VM, use that image with the
included verification helpers and mount read-only full inputs at
`/inputs/full-seed1`, `/inputs/full-seed2` and `/inputs/full-seed3`. Run from the
repository root:

```sh
python3 experiments/a-profile-experiments-20261101/bench-blocks.py --variants control,reserved-reuse-4 --data-seed 2 --blocks 15 --shuffle 1142 --label cap-confirm
python3 experiments/a-profile-experiments-20261101/verify-native.py --variants reserved-reuse-4 --label correctness-cap4
```

The benchmark compiles both sources with matching optimized x86-64-v3 flags and
crate name `solution`. Docker startup and output hashing are outside the timed
interval. The archived report records all shuffle seeds, discarded warmups and
raw runs. Memory measurements use the archived `memory-pairs.py` on the native
host with Docker access, a host `--data` directory, `--variants baseline,reserved-reuse-4`
and a fresh `--report` path. They build the normal pinned Track A Dockerfile and
never report Docker elapsed time as process T.
