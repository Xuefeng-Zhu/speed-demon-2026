# Track D offline PGO trial — isolated, unselected

This experiment builds the exact selected batch16 D source SHA-256 `7fd333be25133a78264cb4b84441de46d4c8bcbfd73914af23761f23d8c47f17`, and uses a byte-identical copy of the official D generator SHA-256 `bbf37741159004149c5896265a98ae00b90e90a05ad48c2912ecf8bdce126d65`. Both Dockerfiles use pinned official Rust 1.99.1 llvm-tools and Debian images, matching Cargo flags, and x86-64-v3. The PGO Dockerfile generates seed-2 sample data inside the offline build using the official Python 3.13 base, runs an instrumented binary, merges with the matching toolchain's llvm-profdata and recompiles in a fresh Cargo target directory. Only the resulting binary is copied to the final image; generator, training data, output, instrumented binary and raw/merged profiles are excluded. Seed 2 is publicly chosen; the unknown holdout seed is not known and not accessed. The source-count exemption, build limits and PGO rules should be rechecked at https://speeddemon.dev/ before adopting.

Two official allowlist static checks, POSIX shell syntax checks, exact source/generator comparisons and SHA256SUMS pass. A non-PGO ARM binary passed tiny seed-2 versus the official reference, 16,000 randomized directed graph answers, and 36,864 exhaustive three-node answers. There has been no Docker build or benchmark of D PGO, no x86 result, no build-time verification and no official cgroup result; PGO matching and relative performance are unknown. PGO does not provide a proof of the selected code's 8 GiB hidden-input cgroup bound. No Docker was run on the Mac.

## Serialized x86 VM procedure

Run on an x86-64-v3 Linux host with Docker already available and with allowlisted images available locally; do not run on the Mac. Build offline in isolated tags, retaining logs and real elapsed times, with pipeline failures propagated (e.g. `set -o pipefail` in bash):

```
docker build --network=none --progress=plain -f context/Dockerfile.control -t sd-d-pgo-control:local context 2>&1 | tee control-build.log
docker build --network=none --progress=plain -f context/Dockerfile.pgo -t sd-d-pgo-trial:local context 2>&1 | tee pgo-build.log
```

Check both image sizes under 2 GB and build times under ten minutes; inspect profile counts, profile-use warnings, Rust/LLVM tool match and runtime final image filesystem. A nonempty profile or distinct binary hash alone does not prove useful profile application. Training host worker count may differ from scoring machine. The v3 feature check deliberately fails if the build host lacks v3; non-native official builds may use a separate machine with unconfirmed support. Inspect the final image to ensure no generator, dataset, answers or profile survives. Extract each `/app/solution` with `docker create` and `docker cp`; remove only those two containers. If host libc is older than the image, run tests in the pinned runtime container without modifying system libraries.

Compare both actual binaries against randomized/exhaustive/large-weight graph oracles and the independent public full seed-1 hash; run paired batches in a free machine window:

```
python3 tools/oracle.py /path/to/control /path/to/pgo
python3 tools/exhaustive.py /path/to/control /path/to/pgo
python3 tools/extremes.py /path/to/control /path/to/pgo
python3 tools/compare.py --baseline /path/to/control --variant /path/to/pgo --data /path/to/full-d --runs 15 --report /tmp/d-pgo-1.json
python3 tools/compare.py --baseline /path/to/control --variant /path/to/pgo --data /path/to/full-d --runs 15 --report /tmp/d-pgo-2.json
```

Also run full input in the official read-only, no-network sandbox, test alternate generated seeds, actual forced pool exhaustion and cutoff/fallback stress. `compare.py` reports native process RSS, not parent-cgroup peak. No performance or all-input correctness claim follows from the static checks.

Parent-run native x86 dot VM PGO tests verified exact selected source, matching Rust/LLVM profile and generator; two paired rounds were 18.0–19.3% slower in wall time, 19.2–20.9% higher in CPU, with increased native RSS. Seventy-two full-seed hashes, eight alternate-reference comparisons, graph oracle, extremes and forced fallback passed. These are native VM measurements, not official cgroup results. This build remains unselected for speed; no claim of target performance is made.
