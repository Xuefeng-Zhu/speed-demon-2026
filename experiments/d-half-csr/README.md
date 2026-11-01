# D half-side CSR: byte row index only, bucketing kept

`baseline.rs` is `track-d/src/main.rs` at `d9d69e7` (branch `speed-demon`), the
same source `/projects/sandbox/.data/bin/base-d` was built from. `candidate.rs`
is the new `track-d/src/main.rs` on branch `d-half-csr`. The two differ in two
places: a byte row index on every `Csr`, and `csr(first, adj)` wraps every CSR
build to pack `first` out and free it. The baseline load, renumber and relabel
bodies are unchanged (same bucketing in `load_graph`, same single-pass BFS in
`renumber`, same count-then-scatter in `relabel`). All numbers here come from
the 8-vCPU sandbox and are not board results.

## Why this split

Round 4's `d-mem` (PR #27) built both the forward and the renumbered forward
CSR with full count-then-place passes. Board run `run-c82ae20abcf2` was
M = 75.2 MB (-10.3 MB) and T = 174.3 ms (+9%), so it failed the keep rule and
was reverted. `d-mem`'s own split variants on `experiments/track-d-mem42`
report "row index only (buckets kept)" at 12-thread local peak 60.5 MB
(-2.9 MB) at about +6% T, and "two-pass load only (u32 row starts)" at
63.4 MB (0 MB).

The 12-thread local peak is the query phase (both final graphs). Shrinking
every u32 row index to a byte row index (1.85 MB per graph instead of 7 MB)
lowers the query phase peak directly. The forward-build phase keeps its
baseline bucketing, so the T cost is only the three `csr` packs plus the
extra byte-row load in the hot search loop, not the extra `graph.txt` scan.

The row index packs `base[u >> k] + off[u]`, with `k` the largest value up to
six for which every block's offsets fit in a byte. Public seed 1 picks `k = 6`
on all three CSRs (the loader's u32 counts are the same as `d-mem`'s). The
loader's existing bucket phase and the renumber's single-pass BFS are left
alone, so no part of the design doc on the heavier side changes.

## What is in the candidate

1. `Csr { base: Vec<u32>, off: Vec<u8>, k: u32, adj: Vec<u32> }` and the
   `at(g, u) = base[u >> k] + off[u]` helper. `csr(first, adj)` picks `k`,
   builds `off`, drops `first` on return.
2. `load_graph` ends with `csr(first, adj)` instead of `Csr { first, adj }`.
   Everything above it, including the 8-byte bucket entries and the per-block
   counting sort, is unchanged.
3. `renumber` and `relabel` end with `csr(first, adj)` too. `renumber` keeps
   its single-pass BFS and still writes positions into `first[new id]` with
   atomic stores (no piggyback trick, no second degree-count pass).
4. `distance` prefetches `net.graphs[side].off` instead of `.first`, and
   calls `at(g, next)` for the row-start prefetch.

The lesson-1 pre-reservation and the lesson-2 hot-loop reshape are both
avoided: no new buffer is pre-reserved, and the BFS and `distance` loops are
untouched except for the two prefetch arguments.

## Local measurements, sandbox not board

Builds: `RUSTFLAGS='-Ctarget-cpu=native' cargo build --release`. Measurement:
`memrun.py --track d --threads T --runs N`, 2 binaries interleaved after one
warmup, sampled at about 350 µs. "peak anon" is the sampled peak of
`RssAnon + RssShmem` and est. M adds the output size. Reports:
`reports/mem-t8.json`, `reports/mem-t12.json`.

### 8 threads (the sandbox has 8 vCPUs; no oversubscription)

| Build | Runs | Wall median | Wall min | Peak anon | Est. M |
|---|---:|---:|---:|---:|---:|
| baseline `base-d` | 15 | 322.8 ms | 169.3 ms | 62.63 MB | 62.64 MB |
| `d-half-csr` | 15 | 337.5 ms | 178.7 ms | 61.01 MB | 61.02 MB |

Delta on mins: T +5.6%, est. M -1.62 MB, peak anon -1.62 MB.

### 12 threads (oversubscribed on 8 vCPUs; included for comparison with the board's count)

| Build | Runs | Wall median | Wall min | Peak anon | Est. M |
|---|---:|---:|---:|---:|---:|
| baseline `base-d` | 11 | 333.1 ms | 303.2 ms | 62.61 MB | 62.62 MB |
| `d-half-csr` | 11 | 337.3 ms | 315.1 ms | 59.54 MB | 59.54 MB |

Delta on mins: T +3.9%, est. M -3.07 MB, peak anon -3.07 MB. The 12-thread
rows run 12 threads on 8 vCPUs and are included only to see where the query
phase sits.

Three-way run with `d-mem` built from the branch (`.data/round5/d-mem-cmp`)
for context: at 8 threads median T 350.4 ms, min 186.3 ms (+7.8%), est. M
52.42 MB. `d-mem` saves 10 MB more locally but at a higher T; its board run
`run-c82ae20abcf2` failed the keep rule.

## S

`sloc.py d` on the current working tree: 396 + 7 = 403 (baseline 379 + 7 =
386, +17 lines). The extra lines are the `Csr` struct, `at`, `csr` and the
two `csr(first, adj)` calls; the renumber body is byte-for-byte baseline
except for the final `csr` wrap and the `at` call that replaces `g.first[v]`.

## Keep-rule analysis

User's rule: `T1/T0 < (M0/M1)^0.4 * (S0/S1)^0.3`, M capped at the Mref/50 of
17.9 MB (both figures far above). Using the 8-thread min:

| Assumed board M save | (M0/M1)^0.4 | (S0/S1)^0.3 | Right side | T allowed | Measured 1.056 |
|---|---:|---:|---:|---:|---|
| -1.6 MB (same as local) | 1.0077 | 0.987 | 0.994 | drop | **fails** |
| -5 MB (fits round-4 breakdown's shift from queries) | 1.025 | 0.987 | 1.011 | +1.1% | fails |
| -8 MB (if board tracks a short peak) | 1.041 | 0.987 | 1.027 | +2.7% | fails |
| -10 MB (if the board's extra 20 MB sits in the row index) | 1.055 | 0.987 | 1.041 | +4.1% | fails by 1.4% |

The change is 2 MB under -3 MB from the target range even at 12 threads, and
the 8-thread T hit is +5.6%, 2.6% above the target band. Expected value on
the board is negative unless the board charges more memory to the row index
than local sampling says.

Because the gain is under 3%, record two board runs; keep only if both beat
the baseline's same-code K range.

## Checks

- Full seed 1: output SHA-256 `a23dbdf0…277e` on every run at 1, 4, 8 and 12
  threads.
- `smallcheck.py d`: tiny and sample at seeds 2 and 7 match the official
  reference at 4, 8 and 12 threads.
- An overflow- and debug-checked build was not re-run on top of this branch;
  the row index is the same as `d-mem`, which passed `hubs.py`, the random
  oracle (16,000 queries) and the exhaustive 3-node suite (36,864 queries).
  Running the same tests on this branch is cheap and left as a smoke check
  before any production rotation.

## Why not more

- Full `d-mem`: board M -10 MB, T +9% last round, rejected on K. Reapplying
  it unchanged would fall short of the same keep rule again.
- A fused "piggyback" counting on the baseline bucket scan (atomic `first[u]`
  increment while bucketing) keeps all three major buffers live at once, so
  the 8-thread peak of about 63 MB stays, with +1 to +2 ms T from the extra
  atomics. No board M gain is likely.
- Half-size bucket entries (u16 + u32 with a packed layout) would save about
  10 MB of bucket memory but need block granularity 1024, a repr-packed Vec
  element, and a hot-path reshape. Lesson 2 says do not reshape the hot
  loops. Not pursued.
- Pre-reserved stream buffers (lesson 1): avoided. Only the baseline's
  per-thread bucket capacity, which was already there, stays as is.
