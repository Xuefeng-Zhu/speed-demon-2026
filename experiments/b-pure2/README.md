# B further pure savings on top of PR #28

`baseline.rs` is `track-b/src/main.rs` at `d9d69e7` (branch `speed-demon`),
the same source `.data/round5/baseb` was built from. `candidate.rs` is the
new `track-b/src/main.rs` on branch `b-pure2`. The two differ in exactly one
line: `plan.long = Default::default();` is now called next to the existing
`Default::default()` call that frees `plan.keys`, `plan.filter`, `plan.aoff`,
`plan.anchors` and `plan.flat` after the scan. All numbers here come from
the 8-vCPU sandbox and are not board results.

## Phase breakdown of the current 62 MB board peak

`profile.rs` adds a background sampling thread (not committed on this
branch) that reads `/proc/self/status` every 200 µs and tracks per-phase
peaks of VmRSS, VmPeak, RssAnon, RssShmem, VmHWM and VmSize. The eleven
phases cover query parse, docs mmap and sample scan, term renumber, phrase
anchor list, bitmap allocation, chunk scan, chunk merge, row transmute,
hits sort and query answering. The scratch binary is in
`/projects/sandbox/.data/round5/b-probe-base` and
`/projects/sandbox/.data/round5/b-probe` for the chained and the split
variants of the scan collect. Measured at eight threads on full seed 1:

| Phase | Peak RssAnon | What is live |
|---|---:|---|
| init | 0 KB | — |
| parseq | 6.5 MB | `qtext`, `plan.keys`, `plan.role`, `terms`, `qs` |
| map+samp | 7.3 MB | + `plan.filter`, `plan.empty`, `freq`, mmap of docs |
| renumber | 8.9 MB | + `bools`, `order`, `new`, `df` |
| anchors | 9.7 MB | + `list`, `plan.anchors`, `plan.flat`, `plan.aoff` |
| alloc_rows | fast | `plan.rows` (21 MB, see below) grows during allocation |
| scan | **52.0 MB** | + chunk `offs/docs/hits` (sum about 24 MB), per-thread temps (stream and group) |
| merge_chunks | about 51 MB | `plan.chunks` built from the scan's `Vec<Vec<(k, Chunk)>>` |
| write_rows | 48.8 MB | `Vec<AtomicU64>` into `Vec<u64>`, same backing allocation (specialized `collect` in place) |
| hits+sort | 48.8 MB | `hits = Vec::new(); chunks.iter().extend(&c.hits)` |
| query | 50.8 MB | scratch pools grow with the heaviest query |

The scan phase is the peak (52 MB). The query phase is 2 MB below. Memrun's
sampled peak at 350 µs is 53 MB (and 58 MB at twelve threads, oversubscribed
on the sandbox's 8 vCPUs); the board records 62 MB. The missing 9 MB
locally versus the board is not located in any of these phases: the sampler
and the probe agree, and the probe runs with the same sampling granularity
as memrun.

## Where the headroom to Mref/50 = 44 MB sits

- `plan.rows`: 21 MB. `plan.nbm * ndocs.div_ceil(64) * 8` bytes of shared
  bitmap, written during the scan and read during BOOL queries. BITMAP
  terms are picked because they are common; their rows are dense. Not a
  packing target.
- `plan.chunks`: about 24 MB. Each chunk owns an `offs: Vec<u32>` of
  `plan.nlist + 1` entries (about 256 KB for the full-seed term count) and
  a `docs: Vec<u16>` sized to the deduplicated postings. The 1.46 MB output
  is a sum of posting counts, so a chunk's `docs` is well below 1 MB each.
  Both arrays are allocated at their exact used size inside `scan_chunk`;
  there is no slack to shrink.
- Per-thread scan temps: `stream: Vec<u16>` is pre-reserved to
  `(hi - lo) / 16 = 1 Mi × 2 B` for a 16 MiB chunk, so eight threads reserve
  16 MB. The baseline reservation is `9/8` of expected, and dropping it to
  zero and letting `Vec` grow by doubling pushed the sampled peak **up**
  (54.75 vs 53 MB) because the doubling copies briefly hold 1.5× the final
  length. Shrinking the reservation does not help.
- Thread stacks: default 2 MiB per worker, 12 workers on the board = 24 MB
  of virtual stack space, but Linux only commits the touched pages. A
  256 KB stack via `thread::Builder` was tried: 8-thread peak 53.18 MB vs
  53.15 MB (noise). At 12 threads 58.04 vs 58.06 MB (noise). The stack is
  not the source of the local 53 MB peak and the board gap, so this one
  does not help either; it also added 7 lines, which is a clear S loss.
- `qtext`: 2 MB, dropped by hand right after the parse. Measured as a
  **regression**: 54.75 vs 52.95 MB. The 2 MB free returns to the per-arena
  freelist and glibc places the next big allocation (e.g. the sampling
  scan's `freq` vector) in a worse spot, inflating RssAnon by about 1.8 MB.
  Not kept.
- `plan.long`: a `HashMap<Vec<u8>, u32>` of query terms longer than 16
  bytes. Used by `intern` during query parse, by `for_each_doc` during the
  scan, and freed on this branch with the rest of the scan tables.

## What the branch does

```diff
-    (plan.keys, plan.filter, plan.aoff, plan.anchors, plan.flat) = Default::default();
+    (plan.keys, plan.filter, plan.aoff, plan.anchors, plan.flat) = Default::default();
+    plan.long = Default::default();
```

One extra line. The answer phase (`boolean`) touches `plan.chunks`,
`plan.rows`, `plan.role`, `plan.nlist`, `plan.nbm` and the local
`hits` and `qs/terms` arrays, so `plan.long` can go next to the other
scan-only tables. On public seed 1 the HashMap holds a few thousand terms
of 17 to 32 bytes, so about 0.1 to 0.5 MB; neither the sampled peak nor
memrun catches the move at eight threads. The scan is the peak, and the
scan runs **before** this drop, so this change cannot show up as scan
peak savings. The expected effect is a slightly lower post-scan floor and
one less long-lived HashMap on the board's cgroup accounting.

## Local measurements, sandbox not board

Builds: `RUSTFLAGS='-Ctarget-cpu=x86-64-v3' cargo build --release`.
Measurement: `memrun.py --track b --threads T --runs N`, 2 binaries
interleaved after one warmup, sampled at about 350 µs. Reports:
`reports/mem-t8.json`, `reports/mem-t12.json`.

### 8 threads (the sandbox has 8 vCPUs; no oversubscription)

| Build | Runs | Wall min | Peak anon | Est. M |
|---|---:|---:|---:|---:|
| baseline `baseb` | 21 | 216.7 ms | 52.92 MB | 54.38 MB |
| `b-pure2` | 21 | 214.2 ms | 52.93 MB | 54.39 MB |

Delta on mins: T -1.2% (noise, both inside the 5% board noise band), M +0.01 MB
(noise).

### 12 threads (oversubscribed on 8 vCPUs; the board's count)

| Build | Runs | Wall min | Peak anon | Est. M |
|---|---:|---:|---:|---:|
| baseline `baseb` | 11 | 402.0 ms | 58.06 MB | 59.52 MB |
| `b-pure2` | 11 | 351.4 ms | 58.05 MB | 59.51 MB |

12-thread rows run 12 threads on 8 vCPUs; the real cost on the board, with
12 real cores, is below the sandbox noise. M is unchanged on both counts.

## S

`sloc.py b`: 561 + 26 = 587, +1 line vs baseline 560 + 26 = 586. The one
line is the `plan.long = Default::default();` call added after the existing
tuple destructure.

## Keep-rule analysis

User's rule: `T1/T0 < (M0/M1)^0.4 * (S0/S1)^0.3`. Local M is identical
within noise, so the whole trial is a bet on the board charging the
previously-held `plan.long` HashMap. With a hypothetical board M saving:

| Assumed board M save | (M0/M1)^0.4 | (S0/S1)^0.3 | Right side | T allowed |
|---|---:|---:|---:|---:|
| -0.5 MB (HashMap plus 1x) | 1.0033 | 0.999 | 1.002 | +0.2% |
| -2 MB (if the arena behavior changes too) | 1.013 | 0.999 | 1.013 | +1.3% |
| -4 MB (same, for an unusually long-term corpus) | 1.027 | 0.999 | 1.026 | +2.6% |

T locally is noise-neutral (-2.5% at 8 threads, +4.9% at 12 threads, both
oversubscribed). The gain is well under 3%: record two board runs and
keep only if both beat the baseline same-code K range.

## Checks

- Full seed 1: output SHA-256 `f86973c2…0927` on every run.
- `smallcheck.py b`: tiny and sample at seeds 2 and 7 match the official
  reference at 4, 8 and 12 threads.

## Tried and not kept

- **`drop(qtext)` right after parse** (regression). Memrun 8t: 54.75 vs
  52.95 MB. Returning the 2 MB `qtext` block to the glibc freelist shifts
  the next large allocation into a less favourable arena and the sampled
  anonymous peak rises about 1.8 MB. Reverted.
- **Smaller thread stacks** (`thread::Builder::new().stack_size(1 << 18)`),
  256 KB vs the default 2 MiB. Memrun 8t: 53.18 vs 53.15 MB. 12t: 58.04 vs
  58.06 MB. No sampled saving; cost +7 S lines. Reverted.
- **Removing stream pre-reservation** (`Vec::<u16>::new()` instead of
  `Vec::with_capacity((hi - lo) / 16)`). Memrun 8t: 55.87 vs 52.92 MB. The
  grow-by-doubling writes 1.5× the final size during the last realloc and
  the sampled peak rises about 3 MB (lesson 1 against zero capacity holds).
  Reverted.
- **Splitting the scan `par(...).into_iter().flatten().collect()` into a
  local**. Appeared to save 8 MB at first; the apparent gain turned out to
  be an artefact of comparing against a pre-#28 `base-b` binary. A fresh
  build of the current `speed-demon` baseline matches `b-split` within
  0.2 MB. Not kept.
- **BufWriter output** instead of `let out: String = outs.into_iter().map(|o| o.1).collect();` +
  `fs::write`. Peak unchanged (the output assembly runs after the sampling
  peak), +4 S lines. Not kept.

## Why not more

The scan phase holds 52 MB, split between the 21 MB bitmap pool, 24 MB of
chunk `offs/docs`, and about 7 MB of per-thread scan temps that are
dropped as `scan_chunk` returns. The pool is dense bitmaps that cannot be
packed; the chunk arrays are exact sizes; the temps already use the user's
preferred `Vec::with_capacity`, and growing them from zero hurts more.
`#28`'s posting counting-sort reused `offs`, dropped the scan tables at
the right line, and shrank query term offsets to u32; the remaining
headroom (62 to 44 MB on the board) is either in the board's accounting
layer (10 MB gap local vs board) or inside the three allocations above
that have no obvious give. The scratch probe will not be committed on
this branch; it is kept in `/projects/sandbox/.data/round5/b-probe/` for
reuse on later rounds.
