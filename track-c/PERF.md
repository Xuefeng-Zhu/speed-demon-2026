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

The restored CRLF implementation passed every gate in official public-seed practice `run-3f3918380bdc` at ebb7061: T=0.128503 s, M=17,321,984 bytes, S=175, K=18.166138 (`experiments/board-ebb.json`). It was faster in this separate run than both batch practices; this is not final holdout scoring.

## Guarded SWAR parser

The selected candidate scans quoted or unquoted field delimiters with guarded unaligned eight-byte reads, and decodes positive comma-terminated IDs with a guarded up-to-seven-digit fast path; longer legal values use the original parser. It retains the locked dictionary and the generator guarantees in §2.2. Exact-source independent review and protected-page tests, 15,145,280 delimiter properties, 10,001,599 integer properties, 19,547 field cases, 20,200,029 unchanged money-parser comparisons, 120 mixed references and 357 hostile record boundaries passed. Parent-run shared native x86 VM paired batches measured 7.4–21.0% lower wall, lower CPU, and unchanged native RSS against `experiments/c-parser-swar/baseline.rs`. Across this and B/D packages, 164 full hashes, 24 alternate comparisons, Linux/AVX2 guard, collision, boundary and graph-oracle checks passed. VM process RSS is not official parent-cgroup memory; official practice follows below.

Official practice `run-58bbcecf9509` at `6e5e00e2a62429b2d6dc63e258a1a35ba666bff8` passed all gates: T=0.115004 s, M=17,747,968 bytes, S=210, D=1, K=18.594109. The preceding exact baseline run `run-11f4d8ed4529` had T=0.128936 s, M=17,911,808 bytes, S=175 and K=18.014565. These separate batches indicate 10.8% lower wall time, subject to normal run variation; final hidden scoring is separate. All four track results are in `experiments/board-6e5e.json`.

## Direct country lookup and region sizing

The selected candidate uses a direct table for the three-uppercase-letter country codes and sizes the region lookup once from its final sorted ID. The existing record parser and dictionary are unchanged. Two independent reviews found no defect under §2.3; reference and adversarial tests covered all 17,576 codes, repeated countries, missing IDs, the maximum generated region ID and different worker counts. The parent-run native x86 VM paired batches measured 6.3% and 4.8% lower wall; a four-way screen measured 18.1% lower wall. Native RSS was approximately 208.7 MiB and unchanged, with mixed CPU results. The VM work passed 136 full executions, 16 alternate comparisons, full-domain/sparse-ID/oracle, collision, 357 boundary and 48,289 guard checks. These are not official scoring-box or cgroup measurements; practice follows below. The previous source is `experiments/c-lookup-direct/baseline.rs`.

Official direct-country practice `run-b88751562923` at `3ee91f3e4d992656829878b41a0ad5c317689a38` passed all gates: T=0.116483 s, M=18,116,608 bytes, S=234 and K=18.103621. Prior guarded-parser baseline batches were 0.115004 and 0.118782 s; the single new batch does not establish an official speed improvement. A same-code repeat follows below. See `experiments/board-3ee91.json`.

The direct-country repeat `run-d2a955c189a1` at `b4f634be302b2044c10d748d2f9b7e446b818fdb` passed all gates with T=0.110389 s, M=17,702,912 bytes, S=234 and K=18.682727. The two direct-country runs were 0.116483 and 0.110389 s versus 0.115004 and 0.118782 s in the previous guarded-parser batches. These are separate practice batches, but the repeat and x86 VM measurements support retaining the speed-focused change. All track results are in `experiments/board-b4f63.json`.

## Guarded AVX2 field scan

The selected candidate adds a 32-byte AVX2 delimiter scan when the compilation target guarantees AVX2 and retains the guarded eight-byte and scalar fallback. It leaves country lookup, quoted-field rules and aggregation unchanged. Independent review and actual x86 protected-page, SIMD, reference and cut tests passed. Parent-run shared native x86 paired batches were 1.1% slower, 27.2% faster and 4.7% faster in wall time, with 3.6–11.5% lower CPU and unchanged native RSS. Across this, A prefix and D chain packages, 300 full hashes and 24 alternate references passed along with relevant collision and graph transformation tests. VM figures are not official scoring-box or cgroup measurements; official practice follows below. The prior exact source is `experiments/c-avx2-rebase/baseline.rs`.

The first AVX2 practice `run-72f4d25c2dee` at `e8276cf1d60c517404eef28b909cedce5a6b293b` passed all gates: T=0.112654 s, M=18,477,056 bytes, S=247 and K=18.188215. The previous direct-country batches without AVX2 measured 0.110389 and 0.116483 s. These separate runs do not establish a clear official wall-time benefit; the same-code repeat follows below. See `experiments/board-e827.json`.

The AVX2 repeat `run-ac5a7e4d8d64` at `c63cebc92eefe31c47801de9224768fd6527b484` passed all gates: T=0.104887 s, M=18,006,016 bytes, S=247 and K=18.947223. The two AVX2 batches measured 0.112654 and 0.104887 s versus 0.110389 and 0.116483 s for the prior two direct-country batches. These independent practice runs vary, but the faster repeat and lower VM CPU support retaining AVX2 for the speed-first objective. All tracks are in `experiments/board-c63ce.json`.

## Salted owner reduction

The selected candidate routes runtime name events to an owner, then reduces each owner’s exact names and group bitsets without shared dictionary locks. Its randomized u64 prehash map promotes chains of more than eight equal hashes into an independently randomized exact-name map. Full byte equality is retained. Encoded names at least 65,535 bytes use a reparse sentinel; file lengths above u32 maximum or group counts at the u16 sentinel select the original sharded algorithm before processing and output. Equal full hashes can still concentrate work on one owner, and randomization is not a worst-case time guarantee.

Independent review and 120 references, 357 record cuts, long-name/sentinel/forced-fallback, country/group boundaries, forced-hash growth, 50,000 same-hash promotion and 16,384 synthetic clustered-prehash tests passed. Parent-run shared x86 VM paired batches measured 28.6–35.9% lower wall, 6.6–7.7% lower CPU and approximately 23.5% higher native RSS. Across this and A compact work, 276 full hashes, 16 full-size all-escape runs, 20 alternates and collision/fallback/guard checks passed. Sparse actual 4 GiB and 4 GiB + 4,096 byte mappings selected the fallback, but full >4 GiB parsing was not tested. VM RSS is not official parent-cgroup memory. The previous exact implementation is `experiments/c-owner-salted/selected.rs`; official practice follows below.

The first salted-owner practice `run-c09e5f674726` at `ba7a690203eddbb3743dc32013a5d7f000f363a3` passed all gates: T=0.094138 s, M=72,445,952 bytes, S=397 and K=14.099074. The immediately preceding AVX baseline `run-ac5a7e4d8d64` measured T=0.104887 s, M=18,006,016 bytes, S=247 and K=18.947223. This single separate-batch comparison is ~10.2% faster but increases cgroup peak about fourfold and lowers K by ~25.6%; it is retained for the explicitly speed-first objective and needs repeat/hidden-data validation. All track results are in `experiments/board-ba7a.json`.

The same salted-owner source was tested again in `run-3ae241b7c74e` at `f78670e1d23a53dcd71567f0e883ebddd95e2cfb`; all gates passed, with T=0.111878 s, M=71,954,432 bytes, S=397 and K=12.950664. The two owner batches were 0.094138 and 0.111878 s; the preceding AVX baseline batches were 0.104887 and 0.112654 s. These variable, separate batches do not establish a consistent official speed gain, while the owner uses materially more cgroup memory and source lines; speed-first testing continues with a further same-code repeat. See `experiments/board-f786.json`.

A third salted-owner batch `run-0f9bc0a6be78` at `e89591928fbfc15db9a303335915a36c86869a47` passed all gates: T=0.092526 s, M=72,691,712 bytes, S=397 and K=14.211733. Owner practice times were 0.094138, 0.111878 and 0.092526 s; the prior AVX baseline batches were 0.112654 and 0.104887 s. Two owner runs were faster than the faster prior baseline, though variation is material. Cgroup peak and code count remain substantially higher and K materially lower (best prior AVX K=18.947223); the owner implementation is retained under the user’s speed-first objective. See `experiments/board-e895.json`.

## Fused name scan and hash

The selected candidate fuses an eight-byte quote scan and streaming hash for ordinary unescaped quoted names; escapes and edge cases use the existing exact field parser followed by the same hash. Both empty encodings use the same hash and all names retain exact byte equality and salted collision promotion. The >4 GiB/group-limit fallback retains its original dictionary. Independent review, 120 mixed references, 357 CRLF/quoted-newline boundaries, long/sentinel/fallback, country, collision, owner and protected-page tests passed. Parent-run shared x86 VM paired batches measured 10.2–10.4% lower wall and 3.5–7.1% lower CPU with unchanged native RSS. Across this and B dynamic/A lookup-order packages, 314 full hashes, 28 alternate references and SIMD/guard/concurrency/collision checks passed. These are not official scoring-box or cgroup measurements; official practice follows below. Equal full hashes may concentrate work on one owner as before. Prior exact source is `experiments/c-fused-namehash/baseline.rs`.

The first fused-scan practice `run-ba9ae3cc89ca` at `8058a98018d3ea75a37faa3bf4064c0963f47934` passed all gates: T=0.087466 s, M=71,622,656 bytes, S=443 and K=14.421293. The immediately prior salted-owner batch `run-0f9bc0a6be78` measured T=0.092526 s, M=72,691,712 bytes, S=397 and K=14.211733. These separate practice batches suggest ~5.5% lower wall, subject to run variation; the owner architecture still has the substantially higher source and memory cost documented above. All track results are in `experiments/board-8058.json`.

The same fused source passed again in `run-52d094d64d33` at `a354194892b3f2b7e4c5db6c52a6f63369fef0c2`: T=0.088358 s, M=71,233,536 bytes, S=443 and K=14.363956. Prior fused practice was 0.087466 s; the high memory/source tradeoff versus the older non-owner architecture remains as described above. See `experiments/board-a354.json`.

The same fused source passed every official gate a third time in `run-087148e92fe4` at `df7f04789962fbc6c25504a10c964f34f6a4b658`: T=0.086697 s, M=71,376,896 bytes, S=443 and K=14.495071. Fused batches were 0.087466, 0.088358 and 0.086697 s; comparisons with prior owner batches are separate, not paired. The higher memory and lower K versus the old non-owner version remain material. See `experiments/board-df7f.json`.

## Owner-local exact-row cache

The trial adds a direct-mapped 32,768-entry `(full hash, stable row)` cache to each active owner. A hit still verifies full hash and exact name bytes; misses use the existing bounded collision chain and salted promotion. Cache state is owner-local and stable row indices survive promotion. The cache adds 512 KiB per active owner on 64-bit systems, plus allocation overhead. The exact previous source is `experiments/c-fused-owner-rebase/baseline.rs`; the independent review and tests are in `experiments/c-rowcache-independent/`.

Independent review found no correctness defect, and an 8,000,000-operation oracle exercised hash collisions, replacement, promotion, exact byte equality and group boundaries with overflow checks. Parent-run native x86 dot VM testing showed 14.3–21.6% lower wall and 21–23.5% lower CPU over three batches, with 1.7–1.8% higher process RSS. All 108 full hashes, eight alternate references, and forced-collision, parser guard, boundary and fallback checks passed. These native VM results are not official scoring or cgroup measurements; full parsing of >4 GiB files remains unverified. The immediately preceding official baseline `run-06f495ecc443` at `f7c90f611b3c6be32cdc0a62d6d8b1623877ddb0` passed all gates at T=0.091259 s, M=71,688,192 bytes, S=443, K=14.115834. The exact candidate is being tested on the official board; results are pending.

The first official owner-cache practice `run-00bb11be4c9b` at `e1a69bebee9aafa73ba36b2ba5dfe0925e13ac3e` passed all gates: T=0.083363 s, M=78,229,504 bytes, S=457 and K=14.445955. The immediately prior no-cache practice was 0.091259 s, M=71,688,192 bytes, S=443 and K=14.115834; earlier no-cache fused batches included 0.086697, 0.088358, 0.087466 and 0.092440 s. These unpaired practices vary, but the first cache run and larger native x86 reductions support retaining the candidate for the speed-first objective. Same-code repeat is pending; see `experiments/board-e1a6.json`.

The same owner-cache source passed every gate in `run-cbb558baf32a` at `5afd571bd74972556df0e445cba076176a8ab660`: T=0.081550 s, M=77,950,976 bytes, S=457 and K=14.616075. Its two official batches were 0.083363 and 0.081550 s, versus previous no-cache fused batches ranging 0.086697–0.092440 s. These are unpaired practices; both the official observations and prior paired x86 VM tests support retaining the cache for wall speed. The earlier no-cache best K was 14.495071. See `experiments/board-5afd.json`.

## Dynamic owner partitions

This trial assigns up to four times as many hash-owned partitions as parser workers, with reducer workers claiming each partition once using an atomic counter. Each partition has its own exact dictionary; identical full hashes still route to one partition. The independent review found no concrete routing or concurrency defect. Parent-run shared native x86 dot VM testing compared the exact `76b341e2` baseline to the `bcd4d771` candidate: paired full-seed wall time was 3.3–7.9% lower, CPU 0.7–1.2% lower and process RSS approximately 1.9% higher. Across C and D packages, 200 full hashes and 20 alternate references passed, along with C long-name, fallback and boundary checks. The two-times partition variant was mixed. These are native VM measurements, not official scoring-box or cgroup results. Equal full hashes can still concentrate work in one partition; the additional partition vectors and allocator peak are not a formal worst-case memory bound. The exact prior source is `experiments/c-rowcache-dynamicparts/baseline.rs`. Official practice follows below.

The first dynamic-partition practice `run-ca974bc25cbc` at `8bd49578b71bd3252b9e4fa8524184ac958faaf7` passed every gate: T=0.095085 s, M=86,749,184 bytes, S=462 and K=13.227845. The previous same-source baseline practices were 0.083363 and 0.081550 s, with 78,229,504 and 77,950,976 bytes respectively. Separate batches vary, and B was also slower in this batch; this single practice conflicts with the paired x86 VM gain. A same-code repeat follows before deciding. See `experiments/board-8bd.json`.

The same dynamic-partition source passed all gates again in `run-39108ebce40c` at `4a3c69459d6adbd21abdef8ccc5ed6c2982600d6`: T=0.081094 s, M=87,187,456 bytes, S=462 and K=14.309123. Dynamic batches were 0.095085 and 0.081094 s; preceding single-partition-per-worker batches were 0.083363 and 0.081550 s. These unpaired official runs overlap and do not establish a stable improvement. The dot VM paired 3.3–7.9% lower wall and fastest official observation support provisional retention for the speed-first goal, with approximately 9 MB greater cgroup peak and lower K than the 0.081550 s baseline batch. Exact baseline is preserved in `experiments/c-rowcache-dynamicparts/baseline.rs`. See `experiments/board-4a3.json`.

## Two-lane parsing

This trial assigns two disjoint CRLF-aligned chunks to each worker, interleaves their record fields while both lanes have data, and processes each remaining tail independently. The exact previous dynamic-partition source is `experiments/c-two-lane-parse/baseline.rs`. Static review and source-instrumented coverage checked collapsed cuts, BOMs, embedded LF, paired and both tail paths, long records spanning multiple cuts and 1/2/3/7/12 workers; forced full-hash collision promotion, long-name sentinel, file/group fallback, protected-page and reference comparisons passed. The Python reference's default field limit stopped an initial 180,000-byte case before comparison; a 100,000-byte case, still above the 65,535-byte sentinel and spanning cuts, passed after adjusting the fixture.

Parent-run native x86 dot VM paired full-seed batches measured 1.1–1.9% lower wall and 0.4–0.6% lower CPU, with native RSS unchanged. Across this and D fixed-bucket packages, 144 full hashes, 16 alternate references, actual x86 guard/reference/oracle checks and natural-capacity exhaustion checks passed. Two full-seed ARM batches had 4.5–4.8% lower wall. These are native results, not official parent-cgroup scores; the x86 difference is modest, so the official single-change practice and repeat are necessary. The preceding dynamic baseline practice `run-2ea1d21854ad` at `7caf8a4b7580cd8668b6302b7d8afdd469bb0640` passed all gates at T=0.078112 s, M=87,248,896 bytes, S=462 and K=14.577643.

The first official two-lane practice `run-8782c9fd2e61` at `f0d9eabd7bdf7fb9ad1f6de671ece6141e5f1989` passed every gate: T=0.079549 s, M=87,658,496 bytes, S=507 and K=14.232039. The immediately prior dynamic-partition baseline was 0.078112 s, M=87,248,896 bytes, S=462 and K=14.577643. These are separate batches; the official difference is small and opposite the native x86 paired 1.1–1.9% improvement. A same-code repeat is pending before a decision. See `experiments/board-f0d9.json`.

The same two-lane source passed all gates in `run-2e654531798d` at `f4419112e1a07a7f3b73e1ee4580517b0bbf1597`: T=0.076229 s, parent-cgroup M=87,302,144 bytes, S=507 and K=14.550509. Two-lane official batches were 0.079549 and 0.076229 s; prior single-lane dynamic batches included 0.078112, 0.082460, 0.081094 and 0.095085 s with S=462. These separate public-seed practices vary, but the faster repeat and paired x86 VM gains support retaining the trial for the speed-first objective. The best prior dynamic K was 14.577643, slightly above this repeat; no hidden-data or worst-case cgroup guarantee follows. See `experiments/board-f441.json`.

## Offline build-time PGO trial

This reversible build-only trial trains an instrumented copy of the exact selected program on sample data generated during the offline build by a byte-identical copy of the organizer's C generator (seed 2), merges a compiler-matched LLVM profile and rebuilds with profile use. The final image copies only the optimized executable. [Organizer rules](https://speeddemon.dev/) permit generator-trained PGO and exempt exact generator copies from source size; no precomputed input answer is used. The previous Dockerfile is `experiments/c-pgo-build17/Dockerfile.selected-before-pgo`.

Parent-run native x86 dot VM tests using Rust 1.99.1 and matched LLVM 23.1.1 profile data found 7.3–8.3% lower wall and 13.1–14.1% lower CPU across two paired batches, with similar native RSS. Across C PGO and the rejected B PEXT3 experiment, 144 full hashes and 20 alternate-reference cases passed; no profile mismatch warnings were reported. These native results do not establish the behavior of this exact Dockerfile. Its three pinned stages passed the official static allowlist check, and selected source and generator bytes matched their tested copies. The Docker build itself, profile use inside it, build time and runtime container remain unverified. In particular, the non-native v3 build may execute on a separate build host that lacks v3, in which case the CPU check/build will fail. Official practice is a reversible trial; retain the previous Dockerfile for rollback and do not assume a hidden-data cgroup bound.

The official PGO practice `run-9d4e5c591ec2` at `d9166c5` passed all gates, built in 26.15 s, and produced a 118,247,567-byte image. It measured T=0.096613 s, parent-cgroup M=87,482,368 bytes, S=526 and K=12.848272; recent non-PGO batches were 0.076702, 0.077594, 0.082476 and 0.084544 s with S=507. The first PGO target result is slower despite VM paired wins, but independent batches vary. Repeat unchanged C PGO while testing B before choosing; the successful public-seed build does not establish every future builder's ISA or hidden-data correctness. See `experiments/board-d916.json`.

The same PGO source and Dockerfile passed every gate again at `261fc62`, `run-c118ea3261b3`, T=0.106485 s, M=87,379,968 bytes, S=526 and K=12.241088. Both PGO target batches (0.096613 and 0.106485 s) were slower than the immediately preceding non-PGO range recorded above, although other tracks also varied and the comparison is not paired. Given those target results, restore the exact previous non-PGO Dockerfile and retain the PGO experiment for future retesting. Full run details are in `experiments/board-261fc.json`.

The restored non-PGO build passed all gates in `run-d973f581cb82` at `8520cf1`: T=0.081327 s, M=87,621,632 bytes, S=507 and K=14.076790. This is faster than both preceding PGO batches (0.096613 and 0.106485 s), though these are separate, variable runs. See `experiments/board-8520.json`.

## Merge of speed-opt source (2026-10-31)

`src/main.rs` replaced with the `speed-opt` version (Dockerfile, .speed-demon.toml and build flags unchanged). Sandbox A/B against `3b1126e` on full seed 1 (2-core arm64, noisy, min of alternating runs, hashes match): no official board run yet for this source. Add the run ID here once the board has scored it, and revert to `3b1126e` if the board T is not better.
Sandbox CPU min: 0.90 s -> 0.63 s.

## Board trial: one-pass AVX2 parser (2026-10-31)

No quote-counting pre-pass (chunks start after a CR), 64-byte AVX2 masks, write-prefetch of name lines 16 records ahead, parallel regions, key-ordered groups. Sandbox CPU about -37%; compare against `b07872c` (`run-11992ecda65c`, T=0.08069 s, M=13.1 MB, S=246, K=23.04) and revert if K is lower.
Result: `run-31d631d51681` at `9bd00f0`: T=0.057728 s, M=13.1 MB, S=310, K=26.32. Kept.

Round-3 trial: name dictionary rebuilt as 2^18 u32 tag index plus one 64-byte line per name (key + group bitset), pipelined probe/prefetch; records.csv read with pread 32 KB chunks instead of mmap (avoids serial 200 MB unmap at exit); read prefetch for shared read-only lines. Local 1-thread CPU 0.335 -> 0.25 s.
Result: `run-f78e7fd076e8` at `b2df83b`: T=0.055621 s, M=35.1 MB, S=339, K=21.71 (was 26.39); time barely moved, memory up 2.6x. Reverted.
Result: `run-e3f84fdfdd7d` at `feadbcc`: T=0.055285 s, M=13.5 MB, S=312, K=26.67 (was 26.30-26.39). Kept.

Round-4 trial (c5): read-only inline name dictionary (dense ids), per-record (name id, country) pairs handed to country-owner threads in 1024 blocks instead of shared atomic OR, read-intent prefetch, fixed-end number parsing.
