# Track C PGO experiment — not selected

This isolated package tests whether Rust profile-guided optimization improves the exact two-lane Track C source. It does not modify the selected submission. The baseline source SHA-256 is `8249f318e26050cc1a12f2be091344bf431ceb862665a3312bb29a92e140057d`; the copied published C generator SHA-256 is `9e61672eb814fa4e1bc2e3cf30c8e7ca9629804191ce5ae60a66c8b61ba704f2`. The package was prepared from repository commit `a4e80b3dac949c16391ff25fc720c41091c4615a`; check source hashes rather than assuming this is still the current branch head.

Both Dockerfiles build the same source with the same pinned Rust 1.99.1 llvm-tools image, Cargo release settings, and x86-64-v3 target. The PGO build generates sample seed 2 from an exact copy of the organizer's generator in an earlier Python stage; instruments the program, trains it, merges raw profiles using the compiler-matched llvm-profdata, and recompiles in a fresh Cargo target directory with `profile-use`. The final image copies only the optimized executable; no training data, aggregates or profile file is copied into it. Seed 2 is independently chosen, not a claim about the unknown holdout seed. The profile selects compiler optimizations and does not recognize inputs or supply answers. The control is the same image and compiler without PGO. The PGO build fails early if the build machine does not expose the required x86 features. The build machine's available thread count may differ from the scoring box's 12, which may change training quality.

The organizer explicitly permits offline PGO training on generator output and makes byte-identical copies of its generator source-size exempt; no cached result or input-recognition shortcut is allowed. See [official rules, Docker contract and FAQ](https://speeddemon.dev/). Verify the current rules and published digest again before a submission. The ten-minute build and 2 GB image limits apply. The build is offline: `/data` is not available and no dependencies or data are downloaded by the build. Docker may need the already-authorized allowlisted base images available on the host before starting the offline build.

## Current evidence and limits

The official Dockerfile allowlist checker passed on both files; each shell-form `RUN` passed `sh -n`. `cmp` verified the copied generator, reference, and source match their originals. A native ARM non-PGO binary passed six generated and hostile official-reference cases using the included `verify_binary.py`. These checks do **not** establish that either Dockerfile builds, that profile data matches the final binary, or that PGO is faster; there has been no Mac Docker, Linux/x86 run, cgroup measurement, official practice or holdout test of this experiment. Inspect `llvm-profdata show --counts` and compilation warnings in the build log to confirm a nonempty useful profile with no serious matching problems. A successful PGO build alone does not prove its profile affected optimization.

## Serialized x86 VM plan

Use an x86-64-v3 Linux VM with Docker already available, and run no competing benchmarks. Confirm the actual host ISA and that an independent official full seed-1 input is available. Do not perform these steps on the Mac. Build the control and PGO images from this package root, retaining logs and elapsed build times:

```sh
docker build --network=none --progress=plain -f context/Dockerfile.control -t sd-c-pgo-control:local context 2>&1 | tee control-build.log
docker build --network=none --progress=plain -f context/Dockerfile.pgo -t sd-c-pgo-trial:local context 2>&1 | tee pgo-build.log
```

Capture each build's exit status correctly in the invoking shell (e.g. Bash `set -o pipefail`). Review profile-use warnings: cold functions may be absent from training, but actual profile metadata mismatches or missing hot-function coverage invalidate the trial. Check the nonzero profile counts, actual elapsed build under ten minutes, and final image sizes under 2 GB. Also confirm the images' runtime filesystem does not contain the training data, generated aggregates, raw/merged profile, generator, or instrumented executable. Training stage data can remain in build cache but must not enter the final image.

Extract each executable using `docker create` followed by `docker cp` from `/app/solution` into separate paths; remove **only the two containers created for this extraction** afterwards. Do not prune or otherwise delete images, containers, datasets, or unrelated files. Check that both extracted files are x86-64 executables and that their SHA-256 hashes differ; different hashes alone do not prove profile usage.

Run reference comparisons against the actual extracted binaries, including generator edge blocks, BOM, embedded LF, escaped quotes, empty fields and a 70,000-byte sentinel name:

```sh
python3 tools/verify_binary.py --binary /path/to/control --binary /path/to/pgo
python3 tools/compare.py --baseline /path/to/control --variant /path/to/pgo \
  --data /path/to/independently-generated-full-seed-1 --runs 15 --report /path/to/first-report.json
python3 tools/compare.py --baseline /path/to/control --variant /path/to/pgo \
  --data /path/to/independently-generated-full-seed-1 --runs 15 --report /path/to/repeat-report.json
```

The comparator checks every full output against the official full seed-1 SHA-256 and uses alternating randomized paired order after warmup; reports include wall/CPU time and native process RSS, **not** official parent-cgroup memory. Also run both final images once in the official read-only, no-network sandbox with full data and compare outputs, then test additional seeds and collision/long-record cases as appropriate. Test profile-use and non-profile paths with target CPU support confirmed. Profile-guided compiler transformations can regress performance and change memory behavior; target practice is required before promotion. More worker-count, >4 GiB, adversarial and hidden-input coverage remains necessary for the selected source, and neither successful tests nor a VM RSS measurement proves an 8 GiB parent-cgroup bound.
