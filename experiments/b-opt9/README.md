# Track B opt9: skip zero result words

The production change adds three lines: skip a zero Boolean-result bitmap word
before calculating its count and ID sum. Each skipped word contributes zero;
word positions, lazy first-ten enumeration and clearing remain unchanged.

- `baseline.rs` is the accepted PR #43 implementation, also byte-identical to
  remote production at `a18078f`: SHA-256
  `c5cced6f876b8c89cb7c11874580c81d60554ce1e73ff7dc8426d0d4fe30ce19`.
- `candidate.rs` is byte-identical to `track-b/src/main.rs`: SHA-256
  `9f97748a1522bbf333cdfe39056a66a5a1ee6c6f34b54854b598fc3c8ac21030`.
- Local formatted Rust count is 622 -> 625. Total S=651 versus 648 is estimated
  until pinned official counting. Dockerfile and dependencies are unchanged.

## Local PGO evidence

Pinned Rust 1.99.1, x86-64-v3, fat LTO, one codegen unit, panic=abort; fresh PGO
training uses official generator seed-2 sample at 12 threads. Both full inputs
use 24 chunks at 12 threads. Execution was Linux x86-64 under Rosetta on ARM
with variable shared-host load. These are emulated measurements, not native
Intel or official T/M/K, and do not guarantee a hidden-seed gain.

| Full input | Measured pairs | Median paired wall change | Paired CPU change | Wall wins |
| --- | ---: | ---: | ---: | ---: |
| seed 1 | 31 | -2.90% | -4.30% | 18/31 |
| seed 2 | 21 | -8.03% | -8.52% | 15/21 |

Every warmup and measured output matched its complete expected hash. Seed 1
uses the published hash. Seed 2 uses the unchanged baseline's hash and an
independent low-memory oracle checking 64 query shapes across all 250,000
documents; that spot check is not independent verification of all 50,000
answers. `oracle.py` and `oracle-full2.json` retain that check.

`source-pgo-t12.json` and `source-pgo-full2-t12.json` retain the original
four-way observations, including rejected combinations. Only baseline/zero
are selected and reproduced by `build-selected.sh`; rejected source variants
are outside this focused change. `build-provenance.json` records exact selected
and baseline source/binary hashes, profile counts, flags and compiler logs.
The selected PGO binary hash is
`ee7ac77635732dd8782126e31af02432552974194c0d07379380cec2a30e1f26`.

Seven fresh restricted x86 containers on seed 2 measured maximum cgroup peaks
of 49,852,416 bytes baseline and 50,307,072 selected (+0.91%). This local
`memory.peak` includes a waiting shell and emulation overhead, so it is not
official M or evidence of a memory reduction. Each run used uid 65534,
read-only root/data, no network/capabilities, 1 GiB memory/tmpfs and 64 PIDs,
and wrote exactly the prescribed output file. Raw readings and hashes are in
`emulated-x86-memory-full2.json`.

## Correctness and reproduction

The selected pinned x86 PGO binary passed 80 organizer-reference comparisons
(20 corpora at 1/2/7/12 threads), 40 additional mixed-reference fuzz corpora,
and three independent 554-expression boundary fixtures (65,536 documents at
one thread and 250,000 documents at eight and twelve threads).

`verify-summary.py` extracts the exact baseline/selected loops, verifies that
all surrounding code is identical, and compares against independent bit
iteration with overflow checks: exhaustive 16-bit patterns at four offsets,
all popcounts, empty/full sets, all 65,536 local IDs and random vectors.

```sh
python3 experiments/b-opt9/verify-summary.py
python3 experiments/b-opt9/verify.py /absolute/solution
python3 experiments/b-opt9/boundary.py /absolute/solution
B_RUST_BINARY=/absolute/solution python3 experiments/b-bounded-fuzz.py "$PWD/experiments/b-rust-positional-adapter.py"
```

For PGO reproduction, mount this repository at `/work` and a fresh writable
directory at `/result` inside the pinned Rust build image from
`track-b/Dockerfile`. Generate seed-2 sample with the unchanged official
`track-b/generator.py` into `/result/training-sample2`, then run:

```sh
sh /work/experiments/b-opt9/build-selected.sh /work /result
```

The driver uses identical offline Cargo settings and fresh profiles for both
sources, validates training outputs, and produces
`/result/opt9-selected-pgo/{baseline,candidate}-pgo-x86`. Use a 2 GiB/no-swap cap
and 600-second timeout. Actual AVX2 execution was verified locally, but Rosetta
hides flags required by the unchanged Dockerfile's CPUID preflight; this is
not a claim that the complete Dockerfile built under emulation.

`bench.py` deletes previous output before each run, validates exactly one file
and its full hash, records kernel CPU/RSS, and calculates within-pair ratios.
Pass `--binary baseline=... --binary candidate=... --threads 12 --runs 31
--report ...`; use `--data` and `--expected` for another verified full input.
`memory-peak.py` reproduces the fresh restricted-container peak checks.

## Experiments excluded from the production change

- Early planning-vector frees initially reduced seed-1 residency but raised
  full seed-2 maximum cgroup memory to 53,706,752 bytes versus 49,852,416
  baseline (+7.73%). Query-map release added no clear cgroup benefit. The
  rejected rows remain in the raw performance/memory reports.
- Full-scale seed-2 PGO training fit the local 2 GiB/600 s build limits but
  measured +3.37% paired wall time versus sample training in 31 seed-1 pairs
  (11 wins). `pgo-scale-t12.json`, `pgo-scale-build.json` and
  `train-pgo-scale.sh` retain its measurements, budget evidence and driver.
  Production retains sample training.
- Sparse enumeration at popcount thresholds 2/3/8 added eleven source lines
  without a stronger result than the three-line zero guard.

No official board or private-holdout performance result exists for this
candidate. The existing short-document chunk-size limitation is unchanged.
