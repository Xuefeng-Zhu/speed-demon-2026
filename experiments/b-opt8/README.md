# Track B opt8: sorted top-ten insertion and cache-line alignment

The selected candidate is based on remote `a3f78a7` (opt7 lean/reuse trial),
which arrived during this experiment. It preserves that version's chunk buffer
reuse, packed atomic count/sum, direct postings iteration and direct output.

- `remote-lean-reuse.rs`: exact remote source, SHA-256 `87561a40a89c1ebcdac2a0a2eeb700a4c7282e9e184cda7085c3851a56332eef`.
- `candidate.rs`: exact selected `track-b/src/main.rs`, SHA-256 `c5cced6f876b8c89cb7c11874580c81d60554ce1e73ff7dc8426d0d4fe30ce19`.

## Selected changes

1. Insert at most ten sorted chunk IDs into the persistent sorted top ten with
   `partition_point` and a slice rotation. This replaces a full ten-element sort
   and relaxed maximum store after every accepted ID with one maximum store.
   Every caller supplies sorted IDs, so a chunk's eleventh ID cannot enter the
   global smallest ten. The existing mutex protects the entire update.
2. Align each Linux accumulator to 64 bytes. Size remains 64 bytes on the pinned
   Linux x86 compiler, while adjacent queries no longer share a cache line.
3. Share term-remap/anchor closures and name the chunk-claim iterator. Local
   rustfmt's Rust code count drops 628 to 622. The previous board total was
   S=654; S=648 is an estimate until the pinned full counter is run. Dependencies
   and the submission Dockerfile are unchanged.

## Local PGO comparison, not official scoring

The binaries use Rust 1.99.1 from the pinned submission build image,
`x86-64-v3`, fat LTO, one codegen unit and panic=abort. Both are trained offline
on the unmodified generator's seed-2 sample with 12 threads. The actual AVX2
path executes on Linux x86-64 under Rosetta on this ARM Mac. These are emulated
measurements, not native Intel results, not official T/M/S/K, and not a board
run. Host load varied substantially during the session.

One warmup and 31 interleaved pairs, full seed 1, 12 threads:

| Metric | Remote a3f78a7 | Candidate |
| --- | ---: | ---: |
| Median wall | 331.24 ms | 306.39 ms |
| Median process CPU | 1.6697 s | 1.5095 s |
| Median process peak RSS | 60.81 MB | 60.26 MB |

Median within-pair wall change: **-5.49%**, 22/31 wins. The ratio of
wall medians is a different statistic; source and environment differences mean
neither establishes a native board gain. Every warmup and measured output
matched `f86973c210228141bcb6f1f1b10188ad2a9b65f71e7cd7cf4590b38de4e80927`.
Process RSS is not the board's cgroup peak-memory metric.

Raw observations: `emulated-x86-final-vs-a3f-t12.json`. PGO binary hashes:
remote `4a34dae583469bb0fb4c6a4f8096515b49e6fd420b79bc16baa39ce415480f0d`;
candidate `d5113cbcbccc3964f0bb71bee242fa71c3d27bba892421fd2c07bebfc75ece90`.

## Correctness and reproduction

The final x86 PGO binary passed 80 organizer-reference comparisons (20 corpora
at 1/2/7/12 threads), another 40 mixed ASCII/Unicode/repeated-phrase fuzz
corpora, and three independent set-algebra fixtures (65,536 docs at one thread;
250,000 docs at 8 and 12 threads, 554 expressions each). The ARM release source
also passed the 80 reference comparisons. Both final accumulator tests passed
on the pinned x86 compiler with overflow checks: 40 shuffled 16-thread merges
and exact Linux size/alignment of 64/64 bytes. A separate restricted runtime
check passed as uid 65534 with read-only root/data, no network, no capabilities,
1 GiB memory/tmpfs and 64 PIDs; it wrote exactly `results.txt` with the full
published hash. That check used the verified amd64 child
`sha256:4876fdea29cac1a33a3195f1eb1952feb1fca7dd6dd00be3e2f1879cf20d34d2`
of the unchanged Dockerfile's pinned Debian index, avoiding the local image
store's ARM/index-digest collision. `final-acc-test.rs` adds a 40-order,
16-thread summary merge check and Linux size/alignment assertions to an exact
copy of the selected source.

```sh
# From this repository, using the existing local Rust compiler:
rustc --edition=2021 -Copt-level=3 -Clto=fat -Ccodegen-units=1 -Cpanic=abort \
  track-b/src/main.rs -o /tmp/b-opt8-final-arm
python3 experiments/b-opt8/verify.py /tmp/b-opt8-final-arm
python3 experiments/b-opt8/boundary.py /tmp/b-opt8-final-arm
B_RUST_BINARY=/tmp/b-opt8-final-arm python3 experiments/b-bounded-fuzz.py \
  "$PWD/experiments/b-rust-positional-adapter.py"
rustc --edition=2021 --test -Copt-level=2 -Coverflow-checks=yes \
  experiments/b-opt8/final-acc-test.rs -o /tmp/b-opt8-acc-test
/tmp/b-opt8-acc-test
```

`pgo-build-final.sh` reproduces both pinned Cargo/PGO builds with the repository
bound at `/work`, a writable working directory at `/result`, and seed-2 sample
training at `/result/training`. The Dockerfile's CPUID-flag preflight cannot be
used under Rosetta because it hides AVX/AVX2 flags; actual AVX2 execution was
verified. This is not a claim that the unchanged full Dockerfile built locally.
`bench.py` records kernel rusage, converts Darwin/Linux RSS units and validates
all full-data outputs. Use `--binary baseline=... --binary candidate=...`,
`--data ... --threads 12 --runs 31 --report ...`.

The pre-existing chunk-size assertion on unusually short 250,000-document
synthetic corpora with four threads remains; the ordinary generator datasets
and the supplied 8/12-thread boundary fixtures pass. No private holdout or
native official-board run has been performed for this candidate.
