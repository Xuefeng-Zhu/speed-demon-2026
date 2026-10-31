# Track B performance and correctness log

Earlier prototype tests used Apple Silicon macOS, `c++ -O3 -std=c++17`, with the official generators and reference. Timings are indicative, not controlled competition measurements.

- Seed 1 sample: exact byte match with official reference; SHA-256 `eeeec1e9319da98a6f3c664c78f93e7078fd603c25c2bb3027174e81e3638a8f`, matching the published hash. One native wall time: candidate 0.53 s; reference 1.68 s. These ran concurrently, so the comparison is approximate.
- Seed 99 tiny: exact byte match with official reference.
- Seed 1 full: exact match with published expected SHA-256 `f86973c210228141bcb6f1f1b10188ad2a9b65f71e7cd7cf4590b38de4e80927`; one native wall time 4.66 s, 4.29 s user and 0.26 s system. `/usr/bin/time -l` could not report peak memory due to sandbox restrictions.
- The private holdout remains unknown. The updated candidate passed the restricted ARM Linux container check on full seed 1 and the emulated x86 sample check. Official board timing and cgroup memory remain unmeasured.

The first subsequent live-board run is recorded at the end.
- A separately generated randomized edge corpus of 300 documents and 6,000 Boolean/phrase queries matched the reference byte for byte. It included repeated terms, uppercase ASCII, non-ASCII separators, operators as terms, and absent terms. The generator was a one-off local test, not a scoring dataset.

## Tokenizer iteration

The original baseline is preserved at `../../track-b-agent/main.cpp` relative to this folder. The candidate uses a fixed 32-byte token buffer (the spec's maximum token length) and looks up `string_view` keys, avoiding construction and per-token management of a `std::string`. The map owns the underlying query strings throughout the scan.

On seed 1 full, three alternating native comparisons yielded baseline 7.479, 4.336, 7.948 seconds and candidate 3.806, 3.198, 6.931 seconds; every output matched the published full hash. Other experiments ran concurrently, and the spread is high, so these do not establish a reliable speedup. Re-run serially without competing processes. Both executables were compiled with `c++ -O3 -std=c++17`.

A separate seed 13 sample (generated with `python3 official/generators/b_index.py --seed 13 --scale sample --out /tmp/speed-b-sample13`) matched the official reference byte for byte; candidate SHA-256 `21b6916ba01887cf204ec1a2be70abc18110f27877c9d425a55a31931df9d2dc`.

To reproduce the comparison from the workspace root, compile `c++ -O3 -std=c++17 track-b-agent/main.cpp -o /tmp/b-baseline` and `c++ -O3 -std=c++17 track-b/main.cpp -o /tmp/b-candidate`. Generate the full seed 1 input with `python3 official/generators/b_index.py --seed 1 --scale full --out /tmp/speed-b-full`. Run each binary with `/tmp/speed-b-full/docs.txt /tmp/speed-b-full/queries.txt /tmp/results.txt` as its three arguments and hash the result; warm the page cache and alternate runs to limit ordering effects. Competition hardware and the official harness remain decisive.

## Controlled local comparison

Five interleaved full-data pairs after warmup on macOS ARM: original median 3.612033 s, then-current serial median 3.118447 s (1.16×). Every output matched the full hash. Details: `experiments/bench-b.json`. These are local measurements, not board scores.

## Native x86 dot VM

The candidate and original were tested on the full seed-1 dataset with GCC 14. See `experiments/dot-vm.md` for the five-run medians and limitations. This was not a board run.


## Native x86 streaming-index follow-up

On a shared dot VM, streaming measured 1.445 s median versus 5.750 s for the prior selected implementation, with peak process RSS 470 versus 337 MiB; the full hash and alternate-reference comparisons passed. The time/memory part of K favors streaming by about 1.87× before source size and dependencies. This is not an official board measurement; see `experiments/dot-vm.md`. The promoted implementation passed the pinned offline restricted ARM Docker full-data check in 2.32 s including startup, fresh tiny seeds 2, 17 and 4242, and independent 1 MiB boundary and 1,000-query edge fixtures. The first subsequent board run is recorded below.


## First official live-board practice run

The public seed-1 practice run at commit `f45c4cf3f707123e705b930c6b1f08b8facefdc5` is `run-29cd387e04b7`. It passed the check, build, correctness, timeout and sandbox gates. The board reports T=1.548718 s, M=495566848 bytes, S=255, D=1, K=6.963181 and 42.140385 machine points. This is a single live-board run, not the final five-run hidden-seed score. Source and snapshot: `experiments/board-f45.json`.


## Live-board practice run at 664ba1a

Run `run-8da2d746f8a0` at commit `664ba1aafb0d765427f49d5ad933b6c1a18b0f24` passed check, build, correctness, timeout and sandbox. The board reports T=1.460408 s, M=495759360 bytes, S=255, D=1, K=7.170064 and 42.776152 machine points. This single public-seed practice run is not final hidden-seed scoring. See `experiments/board-664.json`.


## Live-board practice run at 2fc9110

Run `run-720a9b2e78e9` at commit `2fc9110d0c2acfc880350efbc240f5aa4620bd99` passed check, build, correctness, timeout and sandbox. The board reports T=1.450775 s, M=496271360 bytes, S=255, D=1, K=7.192344 and 42.843522 machine points. This is a single public-seed practice run, not final hidden-seed scoring. See `experiments/board-2fc.json`.


## Bounded phrase-index candidate

The new candidate evaluates phrase matches during indexing, deduplicates identical phrase queries, and retains only per-worker count, sum, first-ten and last-document summaries. On a shared x86 VM, median wall time was 1.541 s versus 1.548 s for the prior streaming candidate, and process RSS 246 versus 470 MiB. Pinned S is 335 versus 255, giving an estimated K ratio of about 1.095 before dependency effects; official cgroup and board measurements remain pending. The campaign reported all full and alternate hashes passed. Independently, the selected code passed the full restricted ARM Docker hash in 2.14 s including startup, tiny seeds 2/17/4242, 1,000 edge queries, 10,000 randomized mixed queries, shard top-ten and six >1 MiB boundary cases, a 250,000-document / 19,000-duplicate-phrase stress and ASan/UBSan differential checks. Many distinct phrases sharing frequent anchors may increase CPU work, so the board timeout and hidden seed remain important. The previous source is `experiments/b-stream-2fc.cpp`; pinned count and Mac evidence are `experiments/b-{selected-664,phrase-bounded}.json` and `experiments/bench-b-bounded.json`.

## Nonlinear packed dictionary candidate

The current candidate replaces only the query-token lookup with zero-padded 32-byte keys, a nonlinear hash and exact full-key comparison. The bounded phrase summaries are unchanged. An initial packed version used a linear hash; a constructed 50,000-term collision family exposed a large CPU penalty, so it was not selected. The nonlinear mixer avoids that particular family but is not a cryptographic worst-case guarantee. The former bounded implementation is preserved in `experiments/b-bounded-1b2.cpp`.

Shared x86 VM medians were 1.198 s for nonlinear packed versus 1.386 s for the preceding bounded code; these native figures are not official cgroup scores. On the constructed collision family, nonlinear took 0.051 s versus 0.803 s for linear packed and 0.052 s for bounded; all outputs matched. The VM campaign also reported 39 alternate comparisons and forced-collision sanitizer checks passing. Pinned clang-format 23.1.3 and scc 4.1.0 counted S=379 versus 335. The candidate matched the full seed-1 hash, a 250,000-document/19,000-duplicate-phrase stress, shard and 1 MiB boundaries, 40 randomized corpora, and forced-collision ASan/UBSan lengths 1–32. Independent review also matched the official reference with the full possible 338,000 distinct query terms and 600 documents under ASan/UBSan. The local Docker socket was unavailable, so the candidate could not be run in a local restricted container; official practice scoring must test that environment. The preceding bounded run at 1b2da3d was `run-75ff44be96e6`: T=1.447820 s, M=256,856,064 bytes, S=335, K=7.883941, all gates passed (`experiments/board-1b2.json`).

Official public-seed practice run `run-ba498e3be31e` at commit `15c6be0476da8dccd0b9cfb8a17bc734552ce419` passed every gate, including build and sandbox: T=1.343342 s, M=256,245,760 bytes, S=379, K=8.038497. The preceding run's K was 7.883941. These separate single practice runs are not final hidden-seed scoring; see `experiments/board-15c.json`.

## Length-aware hashing and nine workers

The speed-focused candidate hashes only occupied 64-bit words of each zero-padded token key, while retaining exact full-key comparisons and bounded phrase summaries; it uses nine index and query workers instead of six. The dot VM measured native medians 0.983 s versus 1.191 s for the six-worker nonlinear baseline, process RSS 261.7 versus 244 MiB. Full hashes, 36 alternate references, randomized/property tests and collision sanitizers passed. These are shared-VM measurements, not official board or cgroup results. The previous source is `experiments/b-length-aware/baseline.cpp`.

Independent review found no defect in the hash length, key bounds or nine-shard merge. An ASan/UBSan test of 250,000 distinct keys and 250,000 lookups, 40 randomized reference corpora, shard top-ten, duplicate and overlapping phrases passed on the exact nine-worker source. The official practice board must measure its runtime, memory and source size; local Mac Docker was not used. At e8e828a, prior B run `run-44b3123b3bcb` passed every gate with T=1.466380 s, M=255,537,152 bytes, S=379, K=7.698133 (`experiments/board-e8.json`).
