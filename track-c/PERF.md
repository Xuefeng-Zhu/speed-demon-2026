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


## Exact hash distinct-count candidate

Per-country open-addressing retains source views and resolves hash collisions by exact byte comparison. A shared x86 VM measured median 0.311 s for this version versus 0.466 s for an independently verified f45 heap baseline. The supplied comparison package's `selected` and `mmap` sources were byte-identical, so its internal comparisons are against mmap; no paired mmap time is inferred from those figures. Pinned formatted S is 213 versus mmap+sort's 198. Local ARM warm-cgroup peaks were approximately 79 MB hash versus 76 MB mmap+sort. These cross-machine results are not a board score.

The selected code passed the pinned restricted ARM Docker full hash in 0.74 s including startup, fresh tiny seeds 2/17/4242, six BOM/EOF/page-boundary fixtures, sample seed 271828 against reference, and a forced-all-hashes-collide ASan/UBSan build on 40 mixed corpora. All 48 full and 16 alternate executions in the user-supplied B/C VM campaign passed across the compared variants. The prior source is `experiments/c-mmap-2fc.cpp`; pinned counts are `experiments/c-hash-static-*.json`, and the collision fixture is `experiments/c-hash-collision-fuzz.py`. Later board runs for that version are recorded below.

## Official practice run at 89795bb

The preceding C++ implementation passed all gates in public-seed practice run `run-919a49a7a449` at commit `89795bbc852b5e24e9f976c7291b3c3a21101361`: T=0.389804 s, M=80,576,512 bytes, S=213, K=7.446852. It is preserved as `experiments/c-mmap-hash-897.cpp`. This is a single practice measurement, not a final holdout score. See `experiments/board-897.json`.

## Checked Rust mapping candidate

This candidate selectively adapts Track C from PR commit `f348fd7227d4afabe6feaf2b7389f7ef73863178`, adding checks for invalid length, MAP_FAILED and null pointers before constructing slices. The PR was not merged. On a shared x86 dot VM the checked mapping median was 0.144 s versus 0.332 s for the C++ baseline; Rust used x86-64-v3 and the C++ comparator used generic ISA, so the measured speed is not attributable only to the algorithm. These are native timings, not official cgroup scores; matching RSS and source count were not supplied.

Cold-file tests used disposable dataset copies and per-file DONTNEED with mincore confirming 0/49,833 pages resident before each run. Three checked mapping and three buffered-read runs all matched the full hash; mmap had ten major faults per run. Cold medians were 0.185 s mmap and 0.255 s buffered. The original PR and its reported SIGBUS environment were not tested, so the report remains unverified and a successful mapping may still fault on later file truncation or I/O errors.

An offline native ARM Cargo build matched the full seed-1 hash. A test-only build forcing all name hashes equal passed 40 mixed CSV corpora, and a separate independent test passed 24 valid corpora at each of five worker counts (120 reference comparisons). These checks cover quoted fields, multiline notes, BOMs, mixed terminators, empty and trailing-space names, unknown regions and exact negative money. x86 alternate, forced-collision sanitizer and quote-boundary tests also passed. Input and output are compared byte-for-byte, and the exact-match implementation resolves hash collisions by key bytes. The official board must still measure this candidate's actual time, memory and source-size coefficient.

The checked Rust release image subsequently matched the full seed-1 hash in a restricted offline ARM Linux container, and the integrated A–D tree matched official reference output on tiny seeds 2 and 17. Pinned scc and host rustfmt 1.9 gave provisional S=170 versus 213 for the previous C++ code; rustfmt was not the pinned 1.10, so the board remains authoritative for S.

Official public-seed practice run `run-e874cd2691bd` at commit `1b2da3d095acd09779f08205f9329f79b7ba40d7` passed every gate: T=0.137394 s, M=17,235,968 bytes, S=170, K=17.662660. The preceding C++ practice run had K=7.446852. These separate single practice runs are not final hidden-seed scoring. See `experiments/board-1b2.json`.

## 1024 dictionary shards

The speed-focused candidate uses 1024 independent dictionary shards instead of 256. On the shared x86 VM its native median was 0.1287 s versus 0.1347 s for 256; all full hashes and 360 independent corpus/worker checks across shard variants passed. These are not official cgroup scores, and the official run must measure time, memory and S. The prior source is `experiments/c-worker-baseline-15c/main.rs`. At 15c6be0 the 256-shard run `run-0af69c4884d5` passed every gate with T=0.136191 s, M=17,403,904 bytes, S=170, K=17.706128 (`experiments/board-15c.json`).

Official practice `run-d8e695246499` at b9c2b54 passed every gate: T=0.135942 s, M=17,813,504 bytes, S=170, K=17.640076. The previous run measured T=0.136191 s; this difference is too small to distinguish from noise. See `experiments/board-b9.json`.

## CRLF record-boundary synchronization

The current candidate aligns partitions after the next CRLF and omits the full quote-parity prepass. This is valid specifically because official spec section 2.2 permits reliance on the generator guarantee for every seed including holdout: CR appears only as the first byte of a CRLF record terminator, and the final record ends CRLF. Bare LF may be record or quoted data and is not used as a synchronization point. This method is not valid for the broader section 2.1 grammar alone. The previous source and test suite are `experiments/c-crlf-boundary/`.

On the shared x86 dot VM, all 64 full runs, eight alternate references and 477 targeted edge/reference comparisons passed. Two randomized 15-pair batches had medians 0.1323 versus 0.1847 s, then 0.1887 versus 0.2035 s, candidate versus previous; RSS was unchanged. Magnitudes varied considerably, so these are native VM observations, not official scoring-box results. At 073646e, prior C practice `run-b6ecbf8e7ae7` passed every gate: T=0.146822 s, M=17,391,616 bytes, S=170, K=17.055466 (`experiments/board-073.json`).

Official public-seed practice `run-86695673615b` at 4f2d688 passed every gate: T=0.137385 s, M=18,157,568 bytes, S=175, K=17.404341 (`experiments/board-4f.json`). The previous run measured 0.146822 s; these separate practice results can vary and are not final holdout scores. An independent test of the exact synchronization function additionally checked 1,561,868 byte-cut positions over 500 mixed fixtures (`experiments/c-crlf-boundary/sync-review.py`).

## Bounded shard batching

The experimental candidate buffers up to 32,768 input-derived name/group references per parsing worker, then acquires each nonempty dictionary shard once per flush. Each shard remains protected while exact name/group bitsets are updated, and worker-local distinct increments are summed afterward. The fixed event buffer and 1,024 heads bound additional per-worker storage; both versions and reproducible tests are in `experiments/c-bounded-batch/`.

On the shared x86 dot VM, two batches were 13.5–18.2% faster with median process RSS 1.8–1.9% higher. Across the B/C/D campaign, all 144 full hashes, 24 alternate references and batch-collision, graph-oracle and Boolean stress checks passed. Independent review of the exact source found no race, lifetime or bounds defect, and it passed another 120 mixed references plus normal/forced-hash 70,037-row/130-group batch-boundary cases. These are native checks, not official cgroup scores. At 8c273db the preceding C run `run-9ce8597de74a` passed every gate: T=0.129274 s, M=17,870,848 bytes, S=175, K=17.999239 (`experiments/board-8c.json`).

Official public-seed practice `run-6fefc73b3633` at 5934716 passed every gate: T=0.134421 s, M=29,593,600 bytes, S=208, K=15.549336 (`experiments/board-593.json`). The 0.005147 s wall regression versus the preceding run conflicts with both VM paired wins, while the measured memory and source factors are higher. A same-code repeat is warranted before choosing on wall speed; these are not final holdout scores.

The same-code repeat `run-a8648a24df86` at b1f947f passed every gate: T=0.137428 s, M=29,286,400 bytes, S=208, K=15.410409 (`experiments/board-b1.json`). Since both scoring-box runs were slower than the earlier 0.129274 s baseline and the user's priority is wall speed, the prior CRLF source was restored. These separate runs are not controlled pairs or final holdout scores.
