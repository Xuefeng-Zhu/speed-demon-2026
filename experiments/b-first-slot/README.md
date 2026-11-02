# Track B: reuse the checked first dictionary entry

The scanner already obtains the home entry with `tbl.get(h)`. The general
probe then repeats table metadata/masking and checks the returned index again
before loading its value. Current-source full-input counts find that about
92.4% of scan lookups finish at that first entry.

This change consumes the existing entry when its complete two-word key matches
or it is empty. On a collision, the original probe continues at the masked
successor. Long-word tags still take the existing long lookup. This adds no
unsafe code or allocation and preserves full-key equality, the query-derived
unknown-term value and packed phrase-anchor bits.

The baseline is kept PR #51 source SHA-256
`82f9199f643947c7ddc1a2a3ef596a45d83770e1488fdf1c8032cb6ef34e572f`.
The tested candidate is
`80036f13d8b3f6f494e38bf4c84d6d1759491fcd690cbdf341a375775e24b4a1`.
Source and build inputs did not change between initial remote `434741c` and
kept base `5639e34`. Formatting adds six Rust code lines; no dependency changes.

## Native measurements

Both sources independently train PGO on the identical seed-2 sample, with the
production pinned Rust 1.99.1/LLVM image, `x86-64-v3`, opt-level 3, fat LTO,
one codegen unit and panic abort. Runtime is the same pinned Debian 13 image.
Exact source/binary/PGO/training/input hashes are in [results.json](results.json).

Runs use the supplied Xeon Platinum 8573C VM, CPUs 0–11 (six physical cores,
twelve SMT threads), `SD_THREADS=12`, and the production 24 chunks. Every run
has a fresh restricted container, read-only root/input, no network, uid 65534,
8 GiB/no swap, and the normal `results.txt` output. Inputs are prewarmed by
the host. A `wait4` parent times the child's complete lifetime, excluding
Docker startup; M is the container's `memory.peak`, not process RSS.

Candidate/control order is randomized and adjacent. Builds/checks/benchmarks
are serialized and the runner waits for other active Docker work. Three rounds
use 9, 20 and 25 measured pairs per seed, with one excluded warmup pair in each
round. All 114 pairs / 228 complete outputs match the expected full hashes.
All measured rows are retained, including slower scheduling samples.

| Paired median change | Seed 1 | Seed 2 |
| --- | ---: | ---: |
| Wall, round 1 (9 pairs) | −1.31% | −1.62% |
| Wall, round 2 (20 pairs) | −1.02% | −3.53% |
| Wall, round 3 (25 pairs) | −1.07% | −1.56% |
| Wall, all 54 pairs | **−1.12%** | **−1.66%** |
| CPU, all 54 pairs | **−1.52%** | **−1.23%** |
| Cgroup peak, all 54 pairs | −0.04% | −0.08% |
| Wall wins | 38/54 | 42/54 |
| CPU wins | 42/54 | 39/54 |

Descriptive paired-bootstrap 95% intervals for pooled wall change are
−1.95% to −0.66% and −2.71% to −0.96%; CPU intervals are −2.08% to −1.22%
and −1.61% to −0.80%. Individual smaller rounds have wider intervals, with
seed-1 wall crossing zero in the confirmations. Three rounds reproduce the
direction and pooled CPU/wall improve on both inputs. The memory observations
are near-neutral. These are shared-VM results; Board confirmation is pending.

Reproduce the saved paired calculations (phase-qualified IDs prevent rounds
from overwriting one another):

```sh
python3 experiments/b-first-slot/analyze.py
```

## Native correctness

The actual PGO baseline/candidate passed 208 general organizer-reference
comparisons plus 40 focused comparisons / 128,480 focused answers, at
1/2/7/12 workers. Focused cases include wrapped real-hash collision clusters,
same-low/different-high keys, unknown words, long-word tags, phrases and 96,000
distinct Boolean terms forcing table growth and the u16 list-term cap.

```sh
python3 experiments/b-first-slot/verify.py --binary /path/to/baseline --binary /path/to/candidate
```

Both exact sources additionally passed 103,157 overflow-checked property
checks each with actual AVX2. The driver appends to the selected source after
renaming only its main function; independent expected results check table
semantics and actual emitted token/anchor values, including forced filter
positives and a first-entry collision sharing all low 64 bits.

```sh
python3 experiments/b-first-slot/make-properties.py track-b/src/main.rs /tmp/b-first-slot-properties.rs
rustc --edition=2021 -Copt-level=2 -Coverflow-checks=yes -Ctarget-cpu=x86-64-v3 /tmp/b-first-slot-properties.rs -o /tmp/b-first-slot-properties
/tmp/b-first-slot-properties
```

The full isolated experiment, native assembly and untrimmed runtime logs are
retained locally under `experiments/b-key-probe-current/`. This PR contains
only the selected probe change and its portable evidence/checks.
