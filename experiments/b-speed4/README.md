# Track B speed4: cheaper scan loop, huge-page term table, deferred answer setup

`baseline.rs` is production Track B at `ec8e317` (PR #43, SHA-256 `c5cced6f…`). `candidate.rs` is the proposed `track-b/src/main.rs` (SHA-256 `1b5cdd57…`, 24 chunks). `candidate-36-chunks.rs` is the same source with `<< 23` (36 chunks), kept as a separate memory option. The chunking, query semantics, bitmap and posting-list plan and output are unchanged; every change is in how the same work is done.

All numbers below are measurements on a profiling VM, not board scores. On the board this source became production Track B as PR #48: `run-56647286efdc` (d4efa0d) T 156.9 ms, M 50.8 MB, S 717, K 29.54 and `run-723a5ea26805` (df9103d) T 151.8 ms, M 50.9 MB, K 30.02, a mean K of 29.78 against 28.87 for #43. The board's T change (about −10%) was about 0.7 of the VM's, while M matched the VM's Docker runs. The 36-chunk variant ran T 166.1 / 163.8 ms with M 41.5 / 41.7 MB (K 29.55 / 29.76) and was not kept.

## Result

| Measurement (seed 1 full unless noted) | Production #43 | Candidate | Change |
|---|---|---|---|
| Native PGO build, 20 interleaved rounds, seed 1 | 148.2 ms | 127.4 ms | −14.1% (median of paired differences) |
| Same, seed 2 | 147.2 ms | 126.4 ms | −13.7% |
| Official Dockerfile build, board `docker run` flags, 12 rounds | 149.8 ms | 129.1 ms | −14.0% |
| M, cgroup `memory.peak` of the Docker runs, median / max | 49.6 / 50.2 MB | 50.3 / 51.4 MB | +0.7 / +1.2 MB |
| M, fresh cgroup per native run, 5 runs, max (seed 1 / seed 2) | 49.7 / 48.1 MB | 50.5 / 49.2 MB | +0.8 / +1.1 MB |
| S, official `static_axes.py` (rustfmt 1.10 + scc): Rust lines | 622 | 691 | +69 (board S 648 → 717) |

The VM's absolute times drifted during the session (production measured 129 ms earlier and 148 ms in the final runs), but the paired change stayed between −12.8% and −14.1% in every comparison of the full candidate against production.

If the board saw the same −14% in T, K would rise by about 5.7%: (1/0.86)^0.5 = 1.078 from T, about 0.996 from M and (648/717)^0.15 = 0.985 from S. The break-even is a board T about 3.8% below production. The board has been harder on some changes than this VM (see "36 chunks" below), so only board runs settle it.

## What changed

Measured step by step during development, as paired medians on seed 1 / seed 2 against the previous step:

| Change | Why | Step change |
|---|---|---|
| Term table in 32-byte slots on 2 MiB pages (`slots()`: anonymous mmap aligned to 2 MiB, `MADV_HUGEPAGE`; the old table is unmapped on regrowth) | The scan's random slot lookups missed the TLB across 768 4 KiB pages. 32-byte slots alone were slower (+2.9% / +3.5%); 24-byte slots on huge pages gave −3.4% / −3.2% | −3.9% / −4.1% |
| Filter test through `std::hint::select_unpredictable`, one hash per token, fixed-size filter view, document id dropped as the line's first token instead of a TAB search, the token carried in from the previous 64 bytes handled once per block, stream written in place | With PGO, LLVM turned the old masked select into a branch on the filter bit, which about 21% of tokens miss. Pass-1 cycles fell about 15% | −3.6% / −4.5% |
| Query terms interned in batches of 64 with their slots prefetched; triggers and accumulators built by one extra thread while the workers scan their first chunks (`OnceLock`) | Parse and intern went from about 7.0 to 5.8 ms, and the workers start about 3 ms earlier | −1.5% / −3.1% |
| Each chunk walks the queries from a different start | Threads no longer update the same `Acc` at the same moment | −1.7% / −1.6% |
| The top-ten update merges the sorted new ids into the sorted ten | One pass instead of an insertion per new id. PR #43's binary-search insertion measured the same within noise; the merge is 2 lines shorter | −1.1% / −1.7% |
| AVX2 count and id sum of a bitmap result (`count_sum`: nibble lookups, `vpsadbw`, `vpmaddubsw`); the scalar loop handles the last words and non-AVX2 builds | LLVM's auto-vectorized six-mask popcount spilled registers | −1.6% / −1.2% |

Ablations on the final file (20 rounds, seed 1 / seed 2, positive means the ablation is slower):

| Ablation | Lines saved | Result |
|---|---|---|
| Production scalar loop instead of `count_sum` | 34 | +1.2% / +3.2%: kept |
| Production `each_token` and TAB search instead of the id-skip and carry changes | 1 | +1.6% / +3.6%: kept |
| A `#[cold]` helper for keys near the end of the data instead of production's padded copy | 3 | −0.9% / +1.1%: not kept, `key()` is production's |

## Measured and rejected

| Variant | Result |
|---|---|
| 16-byte slots with 12-byte keys and an anchor bit (terms over 12 bytes through the map) | +4.8% / +5.1%: lookups got cheaper, but the map path and the per-anchor start lookup cost more |
| Token bounds collected per line before keying | +2.8% / +2.4% |
| List postings counted during the scan instead of in a pass over the stream | +4.2% / +6.8% |
| Stream and bitmap writes fused into the lookup pass | +2.8% / +3.3% |
| Two-pass query parse with prefetch 16 terms ahead | +2.8% / +2.9% (parse 5.5 → 6.7 ms) |
| Repeated BOOL queries answered once | +3.8% / +4.8% |
| Bitmap sum with a branch for words with at most two bits | +2.1% / +2.9% |
| Filter of 2^19 or 2^18 bits instead of 2^20 | +0.9%; +5.1% / +5.5% |
| Slot prefetch issued before the filter test | neutral |
| Bitmap threshold 1/48, 1/64 or 1/96 of sample documents instead of 1/32 | wall within ±2%, cgroup peak +2 to +5 MB |
| 8, 10, 16 or 24 threads instead of 12 | 152, 128, 133, 120 ms vs 110.6 ms |

## 36 chunks

`candidate-36-chunks.rs` (`<< 23`) measured −12.0% / −9.7% against production in the final native runs, 2–5% slower than the 24-chunk candidate, with cgroup peaks of 42.4 / 42.9 MB, under the B memory cap of about 44 MB. On the board, 36 chunks of production #43 ran in 175.9 and 187.9 ms (`run-33cb88f1c6c3`, `run-c6e131974c09`) against 167.9 and 174.3 ms at 24 chunks, so the board may charge more for extra chunks than this VM does. Try this variant only after the 24-chunk candidate has board runs.

## Where the time goes

TSC counters summed over 12 threads, seed 1, one run each, in millions of cycles at 2.3 GHz:

| Phase | Production (`a3f78a7`) | Candidate (before `count_sum` and the rebase) |
|---|---|---|
| Pass 1: tokenize, key, hash, filter, prefetch | 1,093 | 870–910 |
| Pass 2: slot lookups, anchors | 610 | 583–622 |
| Per-document stream and bitmap writes, phrases | 272 | 268–285 |
| CSR build | 257 | 240–250 |
| Answering | 590–630 | 535–556 |

Serial time before the workers start: about 17.6 ms in production, 12.6 ms in the candidate (parse 5.8 ms, filter 0.7, sample 1.4, plan 4.7). Page faults are about 29% of the main thread's samples in that window.

## Method

- VM: Azure, Intel Xeon Platinum 8573C, 8 cores × 2 threads, 32 GB, Ubuntu 24.04, kernel 7.0, THP `madvise`. Every run is pinned to CPUs 0–11, which are 6 cores × 2 threads (siblings 0/1, 2/3, …), like the board's `--cpuset-cpus=0-11`; `available_parallelism()` is then 12. There is no hardware PMU, so profiles use `perf` cpu-clock sampling (`attr.py` attributes samples to `main.rs` lines through inlining) and `rdtsc` counters (`instr.py`, `runstat.sh`).
- Native builds (`vm-build.sh`): Rust 1.99.1, the Dockerfile's toolchain, with `-Ctarget-cpu=x86-64-v3`, fat LTO and the Dockerfile's PGO steps (train on generator seed 2 `sample`, merge with the toolchain's `llvm-profdata`, rebuild).
- `bench.py` runs every binary once per round in a random order on full seeds 1 and 2 with a warm page cache, checks every output's SHA-256 (`f86973c2…0927` for seed 1, `7f224ef6…0869` for seed 2), and reports medians and the median of paired differences against the first binary. `--mem` runs each binary in a fresh cgroup and reads `memory.peak`. Same-binary noise on this VM is about ±1–2% with occasional slow outliers, so differences under 2% are not conclusive.
- `docker-ab.py` checks the Dockerfile with the official `dockerfile_check.py`, builds it with `docker build --network=none`, and runs the image with the flags of the official `harness/run_submission.py` (8 GiB, no swap, read-only root, no network, uid 65534 through `sd-timer`, inputs pre-warmed outside the run's cgroup). This host's Docker uses the systemd cgroup driver, so each run gets its own `kb-<id>.slice` parent and M is that slice's `memory.peak`. It measured production at 49.6 MB median, close to production's board M of 49.4–49.9 MB.
- S comes from the official `harness/static_axes.py` and its tools image. Its total on this VM also counted `generator.py` (919 lines), because the copied harness had no `generators/` folder to recognise the published copy; the board does not count it.

## Correctness

`vmtest.sh` compares against the official Python reference: generated `tiny` seeds 2, 17, 99 and 4242 and `sample` seeds 3 and 13 at 1, 2, 7, 12 and 16 threads; the edge fixtures from 0 to 100,000 documents with independent expected outputs at 1, 2 and 12 threads; and the team's `b-bounded-fuzz`, `b-bounded-boundary`, `b-bounded-shards`, `b-bounded-randomized` and `b-edge-fixture` suites at 1, 4 and 12 threads through `experiments/b-rust-positional-adapter.py`. The PGO and plain builds of the candidate pass all of them except two cases that production fails the same way: an empty `docs.txt`, which the spec excludes and where `mmap` of length 0 fails, and `b-bounded-duplicates.py` (250,000 documents `a a` with 19,000 identical phrases `"a a"`), which needs 4.75 billion phrase hits and is killed for memory. Every timed run of both seeds matched its expected hash. A native macOS ARM build (rustc 1.95, scalar paths, `MAP_ANON` = 0x1000) compiles without warnings and passes the fuzz, boundary, shards, randomized and edge suites against the reference.

## Reproduce

```sh
# on an x86-64 Linux host with rustup 1.99.1 + llvm-tools, gcc and python3
python3 track-b/generator.py --seed 2 --scale sample --out ~/kiro-b/train
cp experiments/b-speed4/baseline.rs ~/kiro-b/src-base.rs; cp experiments/b-speed4/candidate.rs ~/kiro-b/src-cand.rs
bash experiments/b-speed4/vm-build.sh base cand         # plain and -pgo binaries in ~/kiro-b/bin
python3 experiments/b-speed4/bench.py -n 20 -s 1,2 base-pgo cand-pgo
python3 experiments/b-speed4/bench.py -n 5 -s 1,2 --mem base-pgo cand-pgo
bash experiments/b-speed4/vmtest.sh ~/kiro-b/bin/cand-pgo
python3 experiments/b-speed4/docker-ab.py 12 base=<production track-b> cand=<candidate track-b>
```

`bench.py` and `docker-ab.py` expect full seeds 1 and 2 under `~/kiro-b/data/s1` and `s2`. `docker-ab.py` expects the official harness in `~/kiro-b/harness` and `sd-timer` in `~/kiro-b/timer`. `vmtest.sh` expects the official reference and the team's suites under `~/kiro-b/tests/repo` and the edge fixtures in `~/optimize-b-active-20261101/fixtures`.

## Timeline of production #48 (after the board kept it)

`tl.py` adds CLOCK_MONOTONIC events and per-thread `getrusage` to the production source; `tlrun.py` runs it and summarises the median run. The instrumented binary measured within noise of the plain one (−0.9%, 8 paired rounds). Seed 1, VM as above:

| Phase | 12 threads (CPUs 0-11) | 6 threads (one per core) | 1 thread |
|---|---|---|---|
| Wall | 125.4 ms | 149.7 ms | 751.2 ms |
| Spawn to `main` | 1.3 | 1.3 | 1.5 |
| Parse and intern the queries | 6.7 | 6.6 | 6.2 |
| Filter, sample scan, plan | 7.0 | 6.8 | 6.6 |
| Worker phase | 106.7 | 131.3 | 727.7 |
| Output and exit | 3.5 | 3.5 | 9.5 |

At 12 threads each worker scans for 84.2 ms and answers for 20.6 ms, waits 0 ms for the setup thread and idles 1.3 ms on average (2.6 ms at most) after its last chunk; its system time is 2.9 ms. The work before the workers start (13.7 ms) includes about 4 ms of page-fault system time. The worker phase scales 5.54x on 6 cores and 6.82x on 12 threads, so the second hyperthread of each core adds 1.23x.

Phase cycles from `instr.py` (rdtsc, millions at 2.3 GHz, summed over threads; the 12-thread run is the median of 3, the 1-thread run the mean of 2):

| Phase | 12 threads | 1 thread | 12 / 1 |
|---|---|---|---|
| Pass 1: tokenize, key, hash, filter, prefetch | 1,048 (36%) | 605 (35%) | 1.73 |
| Pass 2: slot lookups, anchors | 661 (23%) | 442 (26%) | 1.50 |
| Per-document stream and bitmap writes, phrases | 320 (11%) | 189 (11%) | 1.69 |
| CSR build | 291 (10%) | 159 (9%) | 1.83 |
| Answering | 554 (19%) | 312 (18%) | 1.78 |

One thread spends about 47 TSC cycles (20 ns) per corpus token.
