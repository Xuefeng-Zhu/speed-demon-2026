# Track C performance log

| Step | Change | Run ID | T (s) | M (MB) |
|---|---|---|---|---|
| 0 | Organizers' Python reference | — | 14.44 | 367 |
| 1 | C++ byte parser, direct region map, per-country distinct-name sets | Not run on board | Not measured on board | Not measured on board |

Local validation and local timings are in README.md; the first subsequent live-board run is recorded at the end.

Local revision after step 1: keep canonical name byte views into the input buffer, count note bytes without allocation, and read files directly into a sized buffer. Three interleaved Mac runs improved from 2.833–4.802 s to 1.611–2.730 s; measured peak RSS fell from 687.5–808.9 MB to 354.9–359.3 MB. Other experiments ran concurrently, so repeat on an idle machine. Published seed 1 full and sample hashes and independent reference comparisons still match. These are not board measurements.

## Controlled local comparison

Five interleaved full-data pairs after warmup on macOS ARM: original median 2.636044 s, then-current serial median 1.499528 s (1.76×). Every output matched the full hash. Details: `experiments/bench-c.json`. These are local measurements, not board scores.

Local revision after the hash-set variant: append name views to per-country vectors, then sort and deduplicate. Two interleaved full-data pairs produced 2.641/1.938 s and 352.0/354.6 MB peak RSS for the hash-set version versus 1.142/0.709 s and 293.5/293.0 MB for this variant. All outputs matched the published SHA-256. Other work ran concurrently. That serial candidate also passed the restricted ARM Linux Docker full-data check in 1.27 s including startup; these figures are not board measurements.

## Native x86 dot VM

The candidate and original were tested on the full seed-1 dataset with GCC 14. See `experiments/dot-vm.md` for the five-run medians and limitations. This was not a board run.


## Parallel country sorting

A six-worker pool sorts and deduplicates independent country vectors; ordered output begins only after every worker joins. On a shared native x86 dot VM with GCC 14, the full seed-1 output and alternate-reference cases passed. Five-run median wall time was 0.4376 s versus 0.9685 s for the serial candidate (2.21×); maximum RSS was 269276 KiB for both and median CPU time was 1.007 s versus 0.968 s. These process metrics are local, not official board timings or cgroup memory. The time contribution to K is approximately 1.49× at equal memory; the source-size factor and actual harness results remain unmeasured. The serial implementation is preserved as `experiments/c-serial.cpp`. The first subsequent live-board run is recorded below.

The promoted candidate passed `python3 check.py c --data /tmp/sdc-full --expected d8088b1cd42ba1338b1345b107b55db7b96ef1f5066f3ff64fd26a8912a0f536` under the restricted ARM Linux container: output matched and wall time was 0.84 s including startup. Fresh tiny seeds 2, 17, 99 and 4242 and sample seeds 13, 42 and 76543 matched the official reference; worked and extended parser fixtures passed.


## First official live-board practice run

The public seed-1 practice run at commit `f45c4cf3f707123e705b930c6b1f08b8facefdc5` is `run-9169c3f2e878`. It passed the check, build, correctness, timeout and sandbox gates. The board reports T=0.533652 s, M=278233088 bytes, S=167, D=1, K=5.152004 and 35.598809 machine points. This is a single live-board run, not the final five-run hidden-seed score. Source and snapshot: `experiments/board-f45.json`.


## Live-board practice run at 664ba1a

Run `run-e235d1cc36ec` at commit `664ba1aafb0d765427f49d5ad933b6c1a18b0f24` passed check, build, correctness, timeout and sandbox. The board reports T=0.526909 s, M=277127168 bytes, S=167, D=1, K=5.188997 and 35.754169 machine points. This single public-seed practice run is not final hidden-seed scoring. See `experiments/board-664.json`. This measured the prior heap-copy implementation, preserved as `experiments/c-heap-664.cpp`, not the later mmap candidate.


## Read-only input mapping

The selected candidate maps records rather than copying the full input into an anonymous buffer. The full official hash passed under the restricted ARM container; tiny seeds 2, 17 and 4242 and BOM/EOF/page-boundary fixtures passed against the reference. Independent review, ASan/UBSan, sample seed 99 and the earlier native x86 full/alternate checks also passed. Three alternating warmed-cache local ARM Docker pairs gave cgroup peaks 277,241,856 / 276,971,520 / 277,200,896 B for heap versus 75,550,720 / 76,128,256 / 75,730,944 B for mmap, all hashes correct. A separate prewarmer held the data cache before the measured containers; `experiments/c-cgroup-bench.py` and `experiments/c-cgroup-report.json` preserve the method and data. The supplied x86 wall medians were 0.462 s heap and 0.415 s mmap; pinned formatted S was 167 versus 198. Together those cross-machine local figures imply about 1.33× K, not an official score. The board run above measured heap; mmap awaits its own board run.


## Live-board practice run at 2fc9110

Run `run-a9d0b9f55766` at commit `2fc9110d0c2acfc880350efbc240f5aa4620bd99` passed check, build, correctness, timeout and sandbox. The board reports T=0.527238 s, M=76075008 bytes, S=198, D=1, K=6.548517 and 40.807147 machine points. This is a single public-seed practice run, not final hidden-seed scoring. See `experiments/board-2fc.json`. Compared with the prior heap-copy run `run-e235d1cc36ec`, T changed from 0.526909 to 0.527238 s, M from 277127168 to 76075008 B, S from 167 to 198, and K from 5.188997 to 6.548517 (about 26.2% higher).
