# Track A offline PGO trial — isolated, unselected

This package builds exact selected Track A source SHA-256 `4af40353f517f566217b0f882ec25d8002f61d211dcc479c53f8a1dd5de7ed88`, using a byte-identical copy of the organizer's A generator SHA-256 `d82b43b8f617016808f85cbe9be86af1fee8466296a0848ab8e6908ee3c4b0b4`. Both Dockerfiles use the same pinned Rust 1.99.1 llvm-tools and Debian runtime images, Cargo release configuration and x86-64-v3 target. The PGO build generates public seed-2 sample data inside the offline build, trains an instrumented program, merges with compiler-matched llvm-profdata and recompiles in a fresh target directory with profile use. The final runtime image receives only the optimized executable; generator, inputs, output, instrumented binary and profiles stay out of the final image. Seed 2 is selected independently; the holdout seed is unknown. The organizer permits build-time training on its generated data, exempts byte-identical generator copies from source size, and specifies offline, 10-minute, 2 GB limits: recheck the rules at https://speeddemon.dev/ before adoption.

The official static Dockerfile allowlist checker and `sh -n` checks pass, and `cmp` verifies exact source, Cargo and generator files. A non-PGO native ARM binary (with only Linux anonymous mmap flag adapted for Darwin) passed fresh generated tiny-reference comparisons, the independent synthetic oracle, and reference page-boundary checks. This does not validate Linux PGO compilation, image runtime, profile matching, x86 speed, build duration, or parent cgroup memory. No Docker was run on the Mac. The fixed v3 instrumentation must execute on the build host; a non-native official build may run on a separate builder without v3, in which case the explicit feature check deliberately fails. Do not infer holdout correctness or memory bounds from these tests.

## Serialized x86 VM test

On a compatible x86-64-v3 VM with authorized Docker and pinned images already present, and no competing benchmarks, use this directory as working directory. Do not run Docker on the Mac. Capture real elapsed time and propagate build failures (`set -o pipefail` in bash):

```
docker build --network=none --progress=plain -f context/Dockerfile.control -t sd-a-pgo-control:local context 2>&1 | tee control-build.log
docker build --network=none --progress=plain -f context/Dockerfile.pgo -t sd-a-pgo-trial:local context 2>&1 | tee pgo-build.log
```

Check build times <10 minutes, final sizes <2 GB, matching compiler and llvm-profdata, useful profile counts, and profile-use warnings. Distinct binaries and nonempty profiles alone do not prove helpful profile application. Verify runtime final image has only the optimized executable from build stage and no training input/output, generator, instrumented executable or profile. Extract `/app/solution` from each with `docker create` and `docker cp`; remove only the containers created for extraction, never prune or delete unrelated resources. A newer container libc may not run on the host; use pinned runtime container if needed rather than changing host libraries.

Run actual extracted binaries, including independent generator/reference tests and synthetic, boundary and latency checks, then paired full-data benchmarks in two batches:

```
python3 tools/verify_binary.py --binary /path/to/control --binary /path/to/pgo
python3 tools/test.py --binary /path/to/control --io directories
python3 tools/test.py --binary /path/to/pgo --io directories
python3 tools/page_end_test.py --binary /path/to/control --reference tools/reference.py
python3 tools/page_end_test.py --binary /path/to/pgo --reference tools/reference.py
python3 tools/latency_grid_test.py --binary /path/to/control
python3 tools/latency_grid_test.py --binary /path/to/pgo
python3 tools/compare.py --baseline /path/to/control --variant /path/to/pgo --data /path/to/independently-generated-full-a --runs 15 --report /tmp/a-pgo-first.json
python3 tools/compare.py --baseline /path/to/control --variant /path/to/pgo --data /path/to/independently-generated-full-a --runs 15 --report /tmp/a-pgo-repeat.json
```

Also verify actual images under official read-only/no-network sandbox, full data and multiple worker counts; include compact/escape and long-endpoint forced-collision stress. The comparator removes inherited `SD_THREADS` and records its optional `--threads N` override. It records wall/CPU and native process RSS, not official parent-cgroup memory. PGO's effect and build success remain unmeasured until these tests complete.

Parent-run x86 dot VM offline matched-LLVM PGO comparison showed no repeatable win: 9-worker wall −2.6% then +6.0%, 12-worker +3.4% then −1.2%, with native RSS unchanged. Across 128 full hashes plus reference, boundary and collision tests, outputs matched. These are native measurements, not official cgroup or Docker results. Retain the non-PGO selected build.
