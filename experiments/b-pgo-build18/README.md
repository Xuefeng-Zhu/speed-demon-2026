# Track B offline PGO experiment — unselected

This package compares the exact selected B source (SHA-256 `7d371fe84ce9f0fd9d3c7e6fdf02b6b37e0f1440319c654161b990cf27bb8bf3`) with itself compiled under profile-guided optimization. No selected code is modified. `context/generator.py` is byte-identical to the published B generator, SHA-256 `370ae0d056e3f6d1cf9cd1bf59f5d2ccc0ebcf5745481f904aa55f466850bcdd`.

Both Dockerfiles use the same pinned Rust 1.99.1 llvm-tools image, Rust release flags, x86-64-v3 target and pinned Debian runtime. The PGO build generates seed-2 sample inputs in the offline build, runs an instrumented binary and merges profiles with its own toolchain's llvm-profdata. It recompiles in a separate target directory with `profile-use`. The final image copies only the final executable; generated input, answers, instrumented binary, generator and profile are absent from its final filesystem. Seed 2 is an independently chosen public training seed; the actual holdout seed is unknown. The organizer explicitly allows training on generator output inside offline build and exempts byte-identical published generators from S; verify current site rules, exact pinned allowlist, 10-minute build and 2 GB image limits before adopting. No input recognition or cached answer is used.

## Evidence and limitations

The official Dockerfile allowlist checker passed both files and every shell RUN passed `sh -n`; source and generator `cmp` passed. Using Rust 1.95 native macOS ARM only, an uninstrumented binary matched the official reference on generated seed-2 sample and 40 independent mixed reference corpora. These do not validate PGO compilation, profile applicability, Linux/AVX2 correctness, x86 timing or official cgroup memory. No Docker was used on the Mac. Training host CPU and available parallelism may differ from scoring hardware. `/data` is not available at build time; the training stage generates its own data. This is a hypothesis, not a claimed speedup.

## Dot VM validation (serialized; do not run on Mac)

From this package root, on an x86-64-v3 VM where Docker and the approved images already exist, run the following without competing benchmarks, retaining logs and true pipeline exit status (e.g. bash `set -o pipefail`). No Docker image prune, sysctl change or other unrelated deletion is authorized.

```sh
docker build --network=none --progress=plain -f context/Dockerfile.control -t sd-b-pgo-control:local context 2>&1 | tee control-build.log
docker build --network=none --progress=plain -f context/Dockerfile.pgo -t sd-b-pgo-trial:local context 2>&1 | tee pgo-build.log
```

Verify build durations (<10 minutes), final image sizes (<2 GB), successful nonempty profile counts, matching Rust/llvm-profdata versions and profile-use compilation warnings. Cold functions can be absent, but profile metadata mismatch or absent hot-function coverage invalidates the trial. Different binary hashes alone do not prove effective PGO. Inspect final image filesystem to confirm no training files, answers, profile, generator or instrumented executable is present. Extract `/app/solution` from each with `docker create` and `docker cp`, and remove only the two containers created for that extraction. Debian Trixie binaries may require a newer libc than the VM host; use the pinned runtime container if native loader fails, without modifying host system libraries.

Run tests against each actual extracted binary. From the package root, set `B_RUST_BINARY` to each binary in turn and run:

```sh
B_RUST_BINARY=/path/to/binary python3 tools/b-bounded-fuzz.py "$PWD/tools/b-rust-positional-adapter.py"
B_RUST_BINARY=/path/to/binary python3 tools/b-bounded-shards.py "$PWD/tools/b-rust-positional-adapter.py"
B_RUST_BINARY=/path/to/binary python3 tools/b-bounded-boundary.py "$PWD/tools/b-rust-positional-adapter.py"
B_RUST_BINARY=/path/to/binary python3 tools/b-bounded-duplicates.py "$PWD/tools/b-rust-positional-adapter.py"
python3 tools/compare.py --baseline /path/to/control --candidate /path/to/pgo --data /path/to/full-seed-1 --runs 15 --report /tmp/b-pgo-first.json
python3 tools/compare.py --baseline /path/to/control --candidate /path/to/pgo --data /path/to/full-seed-1 --runs 15 --report /tmp/b-pgo-repeat.json
```

Compare full hashes on every execution and include multiple independent seeds, collision/duplicate stress, line boundaries, forced fallback and actual Linux AVX2 guard-page tests. Test both images in the official read-only/no-network sandbox, and verify profile-use really occurred. Paired VM timings and process RSS are not official scores or parent-cgroup memory. No hidden-data speed, memory-bound or correctness conclusion follows without further evidence. Training data and generated binaries are not included in this archive.
