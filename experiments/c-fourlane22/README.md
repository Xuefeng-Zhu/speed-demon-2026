# Four-lane C parser — unselected experiment

Exact baseline source SHA-256 `8249f318e26050cc1a12f2be091344bf431ceb862665a3312bb29a92e140057d` is the selected two-lane parser. Candidate SHA-256 `f9ac1563ae65b92ef0f22ace2f3862684b82f0380da9d7402c2131bd95530e80` extends it to four disjoint CRLF-aligned input lanes per worker, interleaves the same field steps over all four, and parses each remaining lane tail. Hashing, grouping, event routing, exact-name collision handling, fallback gates and output are unchanged. It relies on the existing official §2.2 CRLF guarantee. It has not been independently source-reviewed, run on actual x86/AVX2, run against the official sandbox, or tested on a full >4 GiB input.

## Local validation and performance

The exact candidate passed 24 mixed corpora across five worker counts against the official reference (120 comparisons), 70 source-instrumented cut/coverage/reference cases with all four tails, collapsed cuts, BOM, LF in quoted notes and 100,000-byte long names, five forced-all-hash-collision/promotion cases, 10 forced file/group fallback references, and the guarded page-boundary field-scan test on native ARM. These are finite checks, not a hidden-input or cgroup proof.

The first nine-pair ARM screen (`arm-screen.json`, ended 13:57:25 UTC) is **contaminated by another agent's compilation/test activity**. The following 15-pair batch (`arm-repeat.json`, ended 13:57:30 UTC) has uncertain overlap with that suite; neither early batch is evidence of a clean speedup. After coordination with both other benchmarking agents, two additional serialized 15-pair warm full-seed screens (`arm-clean-a.json`, `arm-clean-b.json`) produced candidate/baseline wall medians 0.068720/0.073746 s (6.8% lower) and 0.103138/0.104047 s (0.9% lower); median CPU was 0.400363/0.406109 s and 0.460354/0.471979 s. All 64 clean-batch executions including warmups matched the published output hash. Shared-host load differed materially across batches, so these results do not establish a consistent speedup or predict x86/official performance. Native process RSS is not parent-cgroup peak. No Docker was run on the Mac.

## Serialized x86 validation

On a compatible Linux x86-64-v3 machine, independently provide the official full seed-1 dataset. Do not run competing benchmarks. From the package root:

```sh
rustc --edition=2021 -O -C lto=fat -C codegen-units=1 -C panic=abort -C target-cpu=x86-64-v3 experiments/c-fourlane22/baseline.rs -o /tmp/c-fourlane-base
rustc --edition=2021 -O -C lto=fat -C codegen-units=1 -C panic=abort -C target-cpu=x86-64-v3 experiments/c-fourlane22/candidate.rs -o /tmp/c-fourlane-candidate
python3 experiments/c-two-lane-parse/reference.py --source experiments/c-fourlane22/candidate.rs --seeds 24 --avx2
python3 experiments/c-fourlane22/lane-coverage.py --avx2
python3 experiments/c-fourlane22/forced-collision.py --avx2
python3 experiments/c-fourlane22/forced-fallback.py --avx2
python3 experiments/c-fourlane22/guard.py --avx2
python3 experiments/c-two-lane-parse/compare.py --baseline /tmp/c-fourlane-base --variant /tmp/c-fourlane-candidate --data /path/to/full-c --runs 15 --report /tmp/c-fourlane-x86-a.json
python3 experiments/c-two-lane-parse/compare.py --baseline /tmp/c-fourlane-base --variant /tmp/c-fourlane-candidate --data /path/to/full-c --runs 15 --report /tmp/c-fourlane-x86-b.json
```

The comparator checks every run against the published hash and records wall, CPU and native RSS. Confirm actual x86-v3 ISA support first. Review the four-lane loop independently and measure official parent-cgroup behavior separately before promotion; no target, cgroup or final hidden-data result is claimed. The archive contains no datasets, credentials or precomputed scoring answers.

Parent-run dot VM actual x86 paired screens were 1.9% and 1.1% slower than the exact selected two-lane baseline. Across this and B packed-slot, 144 full hashes, actual ISA guard-page and stress checks passed. These are native VM measurements, not official cgroup results; keep the original selected C.
