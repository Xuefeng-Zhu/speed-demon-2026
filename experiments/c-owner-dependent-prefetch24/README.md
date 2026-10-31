# C dependent owner prefetch: unselected

Baseline SHA-256 `8249f318e26050cc1a12f2be091344bf431ceb862665a3312bb29a92e140057d`, candidate `b82a3f980ee59aa72c6cd01c42b096deccd4476bc4a32c116786361705ab8471`. The candidate hints a future direct cache slot, then reads a later future slot and, on a full-hash hit, hints its checked owner-entry and group-bitmap addresses. All updates and exact-byte comparisons still occur in original event order through `see`. Hints never alter the dictionary or output. Extra dependent reads and checks may cost more than they save. This differs from earlier C prefetch experiments that did not hint dependent row and bitmap locations.

Independent static review found no concrete bounds/lifetime or ordering defect: event and cache accesses are checked; row and bit locations are slice-checked after checked arithmetic; each owner is exclusive; entries remain stable indices, and stale hints do not control `see`. This is a hypothesis, not a speed claim or a hidden-data resource proof. The original file/group fallback remains unchanged. A single owner can still receive a collision-heavy workload.

On macOS ARM, where the prefetch helper is excluded, the exact loop structure passed `reference.py --source candidate.rs --seeds 24` (24 corpora × five worker counts) and the public full-seed output hash. ARM does not exercise or benchmark the helper. An extracted copy of the exact helper compiled with Rust to **Windows x86-64-v3 assembly**, containing three `prefetcht0` instructions. This establishes helper syntax and code generation only, not actual Linux x86 execution, safety or speed. An earlier helper compile caught and fixed a raw-pointer type-inference error before the final source. The Linux/x86 guard test below has not been run here. No Docker was run on the Mac.

On a serialized Linux x86-64-v3 VM, verify CPU support before running:

```sh
python3 experiments/c-owner-dependent-prefetch24/guard.py
python3 experiments/c-owner-dependent-prefetch24/reference.py --source experiments/c-owner-dependent-prefetch24/candidate.rs --seeds 24 --avx2
python3 experiments/c-owner-dependent-prefetch24/forced-collision.py --avx2
rustc --edition=2021 -O -C lto=fat -C codegen-units=1 -C panic=abort -C target-cpu=x86-64-v3 experiments/c-owner-dependent-prefetch24/baseline.rs -o /tmp/c-dep-base
rustc --edition=2021 -O -C lto=fat -C codegen-units=1 -C panic=abort -C target-cpu=x86-64-v3 experiments/c-owner-dependent-prefetch24/candidate.rs -o /tmp/c-dep-test
python3 experiments/c-owner-dependent-prefetch24/compare.py --baseline /tmp/c-dep-base --variant /tmp/c-dep-test --data /path/to/independent-full-seed-1 --runs 15 --report /tmp/c-dep-first.json
python3 experiments/c-owner-dependent-prefetch24/compare.py --baseline /tmp/c-dep-base --variant /tmp/c-dep-test --data /path/to/independent-full-seed-1 --runs 15 --report /tmp/c-dep-repeat.json
```

The comparison validates every published full output hash; verify the actual `prefetcht0` path is present and active (e.g. disassembly) and inspect wall, CPU and process RSS. Process RSS is not parent-cgroup peak. Review guard test's actual execution, collision cases, hidden inputs, benchmark variance and official sandbox separately before selecting. No dataset, credentials, generated output or binaries belong in the package.

The portable no-prefetch path also passed the actual three packed parser sites forced to one hash, collision promotion and a long-name sentinel at 1/2/3/7/12 workers against the official reference. The original test script's final print mistakenly said five sites; its loop forced exactly the three sites in this two-lane source and the message was corrected. This test does not run x86 prefetch.

Parent-run x86 dot VM paired full-seed tests showed 5.8% and 5.9% higher wall time than the exact current baseline. Keep the existing selected C. These native results are not official cgroup measurements.
