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
