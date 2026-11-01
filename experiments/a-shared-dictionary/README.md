# Track A shared endpoint dictionary experiments

The inline shared dictionary is selected. `shared-inline.rs` and
`track-a/src/main.rs` are byte-identical, SHA-256
`d0c265b4aa458f4e00336215848115293be62e78d5a9f7d4703b4c8f35687221`.
Native comparisons across three full inputs showed about 4–10% lower paired
wall time at 16 and 20 workers; eight-worker seed-1 results improved about 4%.
The greatest-of-five local container memory peaks fell about 6–9%, and the
formatted Rust count fell from 407 to 398 lines. These are local results;
official scoring-machine T, M, K and hidden-input performance remain unmeasured.

The baseline is the production snapshot captured at `3a7999c`, preserved in
`baseline.rs`, SHA-256
`ce0463894123b026ca924d3de2c3c9a568016b0afbbc7b0c9462659bff87e118`.
Each candidate is independent unless its name explicitly combines changes.

## Changes and correctness arguments

`shared-box.rs` and `shared-inline.rs` replace each parser's private endpoint
table and the 16 shared mutex/hash maps with one append-only, 4,096-slot
dictionary. Each slot uses `OnceLock` to publish one immutable entry containing
the hash, length, dense ID and a 128-byte zero-padded endpoint name. The boxed
variant stores `OnceLock<Box<Entry>>`; the inline variant stores
`OnceLock<Entry>`. Output names borrow the dictionary's owned copies.

- Equal keys follow the same linear probe sequence. A thread encountering a
  slot being initialized waits for that initialization, then compares its full
  hash, length and exact endpoint bytes before returning or advancing. A hash
  collision cannot merge different endpoints, and concurrent discovery cannot
  give one endpoint two IDs.
- Only the winning initializer increments the shared atomic ID counter. With
  successful initialization, IDs form a dense bijection with the published
  entries. The fixed table remains below half full for the specification's
  1,842 endpoints. Initializers never recursively initialize another slot.
- The dictionary's slot vector never grows and initialized entries never change.
  The dictionary outlives the summary plan and every scoped worker, so borrowed
  names remain valid. Names are copied before input pages are advised away.
- Both 64-byte name loads stay inside each entry's 128-byte array, including
  maximum-length names. Exact comparison and the existing compact-record escape
  handling remain intact. Publication uses standard `OnceLock` and `AtomicU32`;
  no custom unsafe atomic state or raw-pointer ownership mechanism is added.
  Existing mapping, SIMD and record-buffer unsafe code remains in scope for
  the original safety requirements.

The shared table eliminates duplicated parser dictionaries, but retains its own
storage throughout summarization. The baseline releases its private dictionaries
at the end of parsing. Fewer dictionary allocations therefore do not establish
a lower whole-run cgroup peak. Boxed entries save empty-slot payload storage;
inline entries remove a pointer indirection. Both perform an initialized-state
check on each lookup, and competing initializers may wait.

Other independent candidates:

| Source | Change | Local formatted Rust code lines |
|---|---|---:|
| `baseline.rs` | Production snapshot | 407 |
| `shared-box.rs` | Shared dictionary with boxed entries | 398 |
| `shared-inline.rs` | Shared dictionary with inline entries | 398 |
| `simd.rs` | SSSE3 decimal-latency conversion for 1–7 digits; original longer-value fallback | 411 |
| `tiny-simd.rs` | One-vector AVX2 ranks for groups 1–8; exact sorting for 9–64 | 401 |
| `bounded.rs` | Baseline with bounded summary/output lookahead | 421 |
| `shared-box-bounded.rs` | Boxed shared dictionary plus bounded lookahead | 412 |

Counts use the local standard-rustfmt method in
`experiments/a-trim/sloc.py`; they are not the complete official S measurement.
All candidates retain the existing larger-group percentile selection behavior.
`tiny-simd.rs` preserves unsigned ordering, ties and genuine `u32::MAX` values;
inactive lanes are masked, and empty groups are skipped by the caller.

## Native x86 timing

The host was an Intel Xeon Platinum 8573C with eight cores and 16 hardware
threads, allowed CPUs 0–15 and no CPU quota. Twenty workers oversubscribe this
host and do not reproduce the scoring machine's topology. The pinned GNU Rust
tool image used Rust 1.99.1. Builds used identical edition-2021, optimization-3,
single-codegen-unit, fat-LTO, panic-abort and `x86-64-v3` settings, including
the same `--crate-name solution`. The baseline and identical-code control had
identical executable SHA-256 hashes in both comparisons.

Every round shuffled the variants, used the same output filesystem, and checked
the full published output hash. Ratios below are medians of per-round
candidate/baseline wall-time ratios; lower is faster. They are not ratios of
separate wall-time medians. Native process RSS is not official parent-cgroup M,
and none of these timings is an official T.

The first screen used 31 measured rounds plus two warmup rounds per worker
setting, shuffle seed 1120. Raw samples, source/binary hashes, CPU and RSS are
in `native-screen.json`.

| Variant | 8 workers | 16 workers | 20 workers |
|---|---:|---:|---:|
| Identical-code control | 1.0068 | 1.0148 | 1.0400 |
| Shared boxed dictionary | 0.9745 | 0.9349 | 0.9560 |
| Shared inline dictionary | 0.9587 | 0.9432 | 0.9368 |
| SSSE3 latency conversion | 0.9967 | 0.9922 | 0.9955 |
| Tiny-group SIMD only | 1.0239 | 1.0160 | 1.0224 |

The follow-up used 51 measured rounds plus two warmups, a new shuffle seed 1121,
and the two bounded-output candidates in place of the latency/SIMD candidates.
Raw evidence is `native-followup.json`.

| Variant | 8 workers | 16 workers | 20 workers |
|---|---:|---:|---:|
| Identical-code control | 1.0050 | 0.9938 | 0.9976 |
| Shared boxed dictionary | 0.9728 | 0.9205 | 0.9391 |
| Shared inline dictionary | 0.9628 | 0.9150 | 0.9494 |
| Baseline plus bounded lookahead | 1.0904 | 1.0206 | 1.0195 |
| Shared boxed plus bounded lookahead | 1.0575 | 0.9673 | 0.9779 |

The boxed and inline dictionary improvements repeated across all three worker
settings. The inline layout is selected after the cross-seed, correctness and
peak-memory checks below. The SSSE3 conversion is close to the timing noise and
adds four source lines; it is rejected. Tiny-group SIMD loses 1.6–2.4% time while
saving only six local lines, so that source tradeoff is also rejected.

Bounding the boxed candidate was slower than the unbounded boxed candidate:
their direct per-round median ratios were 1.0868 / 1.0509 / 1.0305 at
8 / 16 / 20 workers. Its modest memory benefit at 20 workers did not offset the
runtime and source costs against the selected inline layout; bounded lookahead
is rejected.

All 594 first-screen and 954 follow-up output checks passed, including warmups:
1,548 seed-1 benchmark outputs matched
`495ca09682b9673ef836a506496177680bb4a3af54255174befddb1f83481cd3`.

Full seeds 2 and 3 were generated independently. Each comparison used 21
measured rounds plus two warmups at 16 and 20 workers, with an identical-code
control and shuffle seeds 1124 and 1125 respectively. Each full-input expected
output was obtained by executing the captured production baseline on that same
input; these comparisons are baseline differentials, not independent full-input
reference proofs. Input and output identities are in `cross-seed-inputs.json`.

| Selected inline dictionary | 16-worker paired ratio | 20-worker paired ratio | Output checks |
|---|---:|---:|---:|
| Full seed 2, `native-seed2.json` | 0.9047 | 0.9601 | 184 passed |
| Full seed 3, `native-seed3.json` | 0.9292 | 0.9604 | 184 passed |

All 1,916 benchmark output comparisons passed across the first screen,
follow-up and two cross-seed runs. The independent sample/reference checks are
recorded separately below.

## Exact builds and local peak memory

`memory-pairs.py` built all four source contexts with the unchanged pinned
Dockerfile, offline Cargo builds, Docker build networking disabled, and the
native Linux x86-64 GNU runtime. The actual images then ran with read-only input
and root filesystem, no network, uid/gid 65534, all capabilities dropped,
`no-new-privileges`, an 8 GiB memory limit with no additional swap, and a 1 GiB
temporary filesystem. Each run had a private output directory. The host warmed
the input before each run; only the run's own verified output file was removed.

`native-memory.json` records complete source SHA-256 and immutable image
identities, all 40 successful hashes, and five shuffled trials per source at
each worker count, shuffle seed 1122. The inline source identity matches the
selected main source. The table uses the greatest of each five-run set, not its
median:

| Source | 16-worker maximum bytes | 20-worker maximum bytes |
|---|---:|---:|
| Baseline | 26,488,832 | 29,511,680 |
| Shared boxed dictionary | 25,427,968 | 27,353,088 |
| Selected inline dictionary | 24,952,832 | 26,853,376 |
| Shared boxed plus bounded lookahead | 25,112,576 | 26,374,144 |

Inline's measured maximum sets were 5.8% and 9.0% below baseline. The bounded
boxed variant was slightly lower than inline at 20 workers, but higher at 16,
and was slower with more source lines. The combined local time/memory/source
tradeoff supports selecting unbounded inline.

These wrapper/container peaks include the solution, loader, shell/cat wrapper,
and charged output/tmpfs pages. They are not the official parent-cgroup M.
Docker elapsed time is not recorded or presented as process T.

## Properties and backlog diagnosis

`native-validation.json` records successful native checks:

- Both shared layouts passed same-key concurrent discovery, 1,842 forced-hash-
  collision keys across 16 threads, dense-ID bijection, endpoint lengths and
  mismatches, probe wraparound, and borrowed-name ownership after input buffers
  were destroyed. `shared-property.py` exercises the actual candidate sources.
- `simd-property.py` passed 11,000,849 exact SSSE3/fallback value, alignment and
  protected-page checks.
- The exact tiny-group kernel passed 171,476 exhaustive, boundary, padding,
  alignment and random cases. `tiny-simd-property.py` emits the standalone kernel
  property program used for this check.

`native-correctness.json` records all 55 selected-inline checks passing, with the
source and existing native executable identities verified unchanged. The 15
core checks include full seed 1 at 1/2/3/6/8/16/20/default workers, synthetic
oracle, page-end/reference and 132,624-group latency-grid suites, plus sample
seeds 2/98/999/4242 against the official reference. Twenty spec-conforming
adversarial case/worker checks and twenty more with forced endpoint-hash
collisions also passed. These checks supplement the full-input differential
runs; they do not prove correctness on every possible hidden input.

`lookahead-probe.rs` adds counters at plan, completed-hour and write boundaries,
with one final stderr diagnostic and no hot parse-loop instrumentation. Six
diagnostic full-data outputs also matched the published hash. Completed output
held in the channel, receiver or writer peaked at 6.2–6.3 MB of payload at
16 workers and 7.2–8.1 MB at 20. Receiver-only pending payload peaked between
2.4 and 7.2 MB across these runs.

These are independent high-water marks, not simultaneous measurements of
cgroup M. Vector capacity can include untouched reserved pages. The probe also
reported about 20.1–20.2 MB of parsed record capacity and 10.1 MB of final output.
Blocking later summary work retains record chunks that would otherwise be
freed—roughly 278 KB of record capacity versus 140 KB of output per average
hour. A smaller output queue can therefore increase total peak memory.

The bounded prototypes use a mutex/condition-variable gate with a fixed window
of `SD_THREADS * LOOKAHEAD_FACTOR`, currently factor 1. A worker releases the job
mutex before waiting and releases the gate before computing or sending output.
The writer advances the gate only after contiguous successful writes. The
earliest unwritten hour is always eligible, including at one worker; spurious
wakes recheck the condition. The baseline's two barriers and release
`panic=abort` behavior remain intact. No unwind-recovery mechanism is promised.

## Reproduction

`make-shared.py` recreates the boxed and inline snapshots from `baseline.rs`;
choose `shared-inline.rs` to reproduce the selected main source. Run the
following serially from the repository root in the pinned native x86 GNU Rust
environment, with independently generated full seeds 1, 2 and 3 mounted
read-only at the runner's `/inputs/full-seed1`, `/inputs/full-seed2` and
`/inputs/full-seed3` locations:

```sh
python3 experiments/a-shared-dictionary/make-shared.py
python3 experiments/a-shared-dictionary/run-native.py
python3 experiments/a-shared-dictionary/verify-native.py --variant shared-inline
python3 experiments/a-shared-dictionary/cross-seed.py
```

`run-native.py` runs properties, the first native screen and the diagnostic
probe. The follow-up uses `experiments/a-x86-speed/bench.py` with variants `baseline`,
`control` (also `baseline.rs`), `shared-box`, `shared-inline`, `bounded` and
`shared-box-bounded`, identical `--crate-name solution` arguments, threads
`8,16,20`, 51 rounds, two warmups and shuffle seed 1121.

Run the memory helper separately on the native host with Docker and the full
seed-1 input location configured in the helper. It refuses to start alongside
any running container and stores its contexts/build logs under its own `target/`:

```sh
sudo python3 experiments/a-shared-dictionary/memory-pairs.py --data /path/to/full-seed1
```

The exact selected source has passed the local native timing, cross-seed,
correctness and hardened-image checks described above. Official practice is
still required to establish scoring-machine T, M and K; hidden-input outcomes
remain unknown.

`validation.json` records the selected source and report identities;
`verification-logs.tar.gz` preserves
the raw property and 55-check logs, whose recorded hashes were rechecked locally.
