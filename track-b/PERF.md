# Track B performance and correctness log

Earlier prototype tests used Apple Silicon macOS, `c++ -O3 -std=c++17`, with the official generators and reference. Timings are indicative, not controlled competition measurements.

- Seed 1 sample: exact byte match with official reference; SHA-256 `eeeec1e9319da98a6f3c664c78f93e7078fd603c25c2bb3027174e81e3638a8f`, matching the published hash. One native wall time: candidate 0.53 s; reference 1.68 s. These ran concurrently, so the comparison is approximate.
- Seed 99 tiny: exact byte match with official reference.
- Seed 1 full: exact match with published expected SHA-256 `f86973c210228141bcb6f1f1b10188ad2a9b65f71e7cd7cf4590b38de4e80927`; one native wall time 4.66 s, 4.29 s user and 0.26 s system. `/usr/bin/time -l` could not report peak memory due to sandbox restrictions.
- The private holdout remains unknown. The updated candidate passed the restricted ARM Linux container check on full seed 1 and the emulated x86 sample check. Official board timing and cgroup memory remain unmeasured.

The first subsequent live-board run is recorded at the end.
- A separately generated randomized edge corpus of 300 documents and 6,000 Boolean/phrase queries matched the reference byte for byte. It included repeated terms, uppercase ASCII, non-ASCII separators, operators as terms, and absent terms. The generator was a one-off local test, not a scoring dataset.

## Tokenizer iteration

The original baseline is preserved at `../track-b-agent/main.cpp` relative to this folder. The candidate uses a fixed 32-byte token buffer (the spec's maximum token length) and looks up `string_view` keys, avoiding construction and per-token management of a `std::string`. The map owns the underlying query strings throughout the scan.

On seed 1 full, three alternating native comparisons yielded baseline 7.479, 4.336, 7.948 seconds and candidate 3.806, 3.198, 6.931 seconds; every output matched the published full hash. Other experiments ran concurrently, and the spread is high, so these do not establish a reliable speedup. Re-run serially without competing processes. Both executables were compiled with `c++ -O3 -std=c++17`.

A separate seed 13 sample (generated with `python3 official/generators/b_index.py --seed 13 --scale sample --out /tmp/speed-b-sample13`) matched the official reference byte for byte; candidate SHA-256 `21b6916ba01887cf204ec1a2be70abc18110f27877c9d425a55a31931df9d2dc`.

This historical comparison used C++ candidates. Generate the full seed 1 input with `python3 official/generators/b_index.py --seed 1 --scale full --out /tmp/speed-b-full`. The subsequent selected C++ source is preserved in `experiments/pr1-c634/baseline-track-b/main.cpp`; the current Rust candidate uses directory overrides as documented in `README.md`. Competition hardware and the official harness remain decisive.

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

Official practice `run-6f8f977f36f7` at e6e72ac passed every gate: T=1.124940 s, M=274,243,584 bytes, S=379, K=8.665777 (`experiments/board-e6.json`). The previous practice was 1.466380 s and K=7.698133; these separate single public-seed runs are subject to noise and are not final holdout results.

## Proposed bounded Rust PR merge

The selected merge candidate adapts PR head c634a2a to deduplicate identical phrases and retain bounded per-chunk summaries, cap aggregate bitmap payload at 64 MiB with exact postings fallback, and use nonlinear hashing with full-key equality. The unmodified PR B is preserved outside the submitted track as `experiments/pr1-c634/track-b.rs`; the preceding C++ source is `experiments/pr1-c634/baseline-track-b/main.cpp`. The candidate passed full seed-1, 250,000-document/19,000-duplicate-phrase, maximum query-vocabulary, forced-collision, 240 corpus/worker and forced-cap reference checks. Shared x86 dot VM paired medians were 0.39674 s and 151,300 KiB process RSS versus 0.99440 s and 268,012 KiB for the C++ baseline; hashes and references passed. Native VM observations are not official sandbox, cgroup or source-score measurements.

Official public-seed practice `run-6911d7d41e73` at merge commit d144adc passed all gates: T=0.394683 s, M=225,353,728 bytes, S=343, K=15.445575. The previous B practice measured T=1.124940 s, M=274,243,584 bytes, S=379, K=8.665777 (`experiments/board-e6.json`). These separate runs are not final holdout scores; see `experiments/board-d144.json`.

## Eight-byte transition scanner

The current speed candidate classifies eight bytes at a time and visits token transitions; it retains exact dictionary key comparisons, bounded phrase summaries and the capped bitmap fallback. Under the documented tokenizer, high bytes remain separators and reads stay within a document line. The previous source and property checks are in `experiments/b-swar-transitions/`.

Two paired dot VM x86 passes showed 3.0–6.1% lower wall time; all 112 full hashes, 16 alternate references and supplied B scanner/C collision stress passed across that campaign. Independent review found no defect, and 48 constructed corpora at each of 1/2/7/16 workers matched the official reference with overflow checks, including ASCII punctuation, UTF-8 separators, empty documents and token lengths around every eight-byte boundary. A separate overflow-checked property test exercised 4,816,896 byte/lane cases, all 65,536 ASCII masks and 100,000 random vectors. The native VM measurements are not official scores. At 4f2d688, the prior B practice `run-a07e3a7b9261` passed all gates with T=0.403564 s, M=218,177,536 bytes, S=343, K=15.373863 (`experiments/board-4f.json`).

Official public-seed practice `run-4032632a8fcf` at 147d5b4 passed all gates: T=0.381505 s, M=222,068,736 bytes, S=399, K=15.402876 (`experiments/board-147.json`). The preceding run measured T=0.403564 s and K=15.373863. These separate practice measurements are not final holdout scores.

## AVX2 tokenizer

The speed-focused candidate classifies guarded 32-byte blocks with AVX2 when available, with a scalar fallback, and finds line ends with libc `memchr`. Every vector load is bounded by the current line; token runs crossing blocks retain their start, non-ASCII bytes remain separators and exact key comparisons are unchanged. Bounded phrase summaries, bitmap cap and query logic are unchanged. The previous eight-byte scanner is `experiments/b-swar-transitions/transitions.rs`.

On the shared x86 dot VM, the actual AVX2 path passed classifier equivalence, guard-page, alignment, forced-worker, fuzz/duplicate tests, 56 full hashes and eight alternate references. Against the selected eight-byte scanner, two paired batches were 18.6% and 11.2% faster respectively, with CPU 15.8% lower and process RSS roughly 2–4% higher. These are native VM observations, not official cgroup scores. Independent source review found no bounds, fallback or concurrency defect; overflow-checked scalar builds matched the reference on 4,120-document and separate 3,072-document alignment fixtures.

Official public-seed practice `run-2412f1eeaa55` at b07315c passed all gates: T=0.341042 s, M=222,486,528 bytes, S=427, K=16.120054 (`experiments/board-b073.json`). The preceding practice measured 0.381505 s and K=15.402876. These separate runs are not final holdout scores.

## Exact short-token lookup

The current candidate adds an immutable open-addressed lookup for query terms of at most eight bytes and retains the full-key table for longer terms. Legal tokens contain only nonzero ASCII alphanumerics, making zero-padded short keys unambiguous; exact comparisons resolve collisions. Reads are slice-bounded and the 64 MiB bitmap cap and bounded phrase summaries are unchanged. The preceding source and portable tests are `experiments/b-short-lookup/`.

On the shared dot VM, two paired x86 passes measured 7.8–9.3% lower wall time, 9.7–11.3% lower CPU and roughly 1.3–1.4% higher process RSS than the AVX2 baseline. The actual AVX2 path passed guard-page, alignment, classifier, collision/property, vocabulary and duplicate stress, 56 full hashes and eight alternate references. Independent review found no defect and passed 90 additional overflow-checked reference corpora and forced-all-collision properties. These VM results are not official scores; the board must measure runtime, memory and source count.

Official practice `run-60df0a3a64c3` at 23ffdfc passed every gate: T=0.346703 s, M=223,195,136 bytes, S=478, K=15.709610. The previous official run was 0.341042 s with K=16.120054 (`experiments/board-b073.json`). Because this small single-run loss differs from the two dot VM paired wins, the candidate remains selected for a further scoring-box measurement rather than claiming a reliable improvement. See `experiments/board-23f.json`.

Same-code official repeat `run-ce99b40ddc51` at e88ee2c passed every gate: T=0.315290 s, M=224,714,752 bytes, S=478, K=16.451282 (`experiments/board-e88.json`). The 23ffdfc and e88ee2c runs used identical selected source and Dockerfiles. These separate public-seed practices vary; together with two dot VM paired wins, they support retaining the short-token table for wall speed, but are not final holdout scores.

## Dense Boolean summaries

The current candidate computes count and ID sum for dense bitmap words using popcount masks, while sparse words still visit individual bits and the first ten IDs remain ascending. Phrase summaries, strict left-to-right Boolean evaluation and the bitmap cap are unchanged. The exact previous source, proofs and tests are in `experiments/b-bitstats/` and `experiments/b-bitstats-independent/`.

Two paired x86 dot VM batches reported wall time 1.4–6.8% lower and CPU time 4.9–6.1% lower, with process RSS roughly unchanged. All 56 full hashes, eight alternate references, AVX2/guard-page, exhaustive/random masks, forced dense/sparse and cap-fallback, collision and duplicate checks passed. Independent review found no defect and checked 65,536 exhaustive and 200,000 random bit masks plus overflow-checked references. These are native VM observations, not official scores.

Official public-seed practice `run-e221a0a52bd3` at 8c273db passed all gates: T=0.303369 s, M=223,789,056 bytes, S=496, K=16.692436. The prior run measured T=0.315290 s and K=16.451282. These are separate practices, not controlled pairs or final holdout scoring; see `experiments/board-8c.json`.

## Four-way short-token dictionary

The isolated candidate groups four exact short-token keys in one 64-byte-aligned slot and compares them with AVX2 on the official x86-64-v3 build, while portable builds use scalar equality. It retains exact collision probing, bounded phrase summaries and existing Boolean handling. Independent review and normal/forced-collision key properties, mixed references, tokenizer alignment, duplicate-phrase stress, and Linux AVX2 protected-page checks passed. The parent-run shared native x86 VM paired batches measured 1.9–3.0% lower wall time than `experiments/b-group4-short/baseline.rs`. Across this, C parser and D mmap packages, 164 full hashes, 24 alternate comparisons, guard-page, collision, boundary and graph-oracle checks passed. VM performance is not official scoring-box performance; official practice follows below.

The first official practice `run-88c8b8610117` at `f21df30d1e9ff3c8b17d60eef772dc4a2b3f954a` passed all gates but measured T=0.364905 s, M=219,140,096 bytes, S=538, D=1, K=15.098845; the immediately preceding baseline run `run-30ef886ae636` was T=0.301393 s, M=222,109,696 bytes, S=496 and K=16.772315. These are separate batches; the same-code repeat follows below. See `experiments/board-f21.json` for all tracks.

The same-code repeat `run-afa59bdea30c` at `385a0d75ffc147fffec10013dfeebc7987fd39a8` passed all gates with T=0.302563 s, M=229,113,856 bytes, S=538 and K=16.434626. Compared with the previous baseline batch at 0.301393 s, this showed no official speed gain; the first grouped batch was slower at 0.364905 s. Separate batch timings vary, but the original lookup was restored for the speed-first objective. The tested grouped candidate remains in `experiments/b-group4-short/candidate.rs`, and all results are in `experiments/board-385a.json`.

## Guarded CRC short-token hash

The isolated candidate uses SSE4.2 CRC32C as a short-token hash on the x86-64-v3 target, retaining complete byte equality. It rejects the trial table and rebuilds with the original hash if insertion displacement exceeds 32 or any cyclic occupied cluster exceeds 64; non-SSE4.2 builds retain the original hash. Independent review and forced collisions exercised exact threshold boundaries and cyclic wraparound. The parent-run shared x86 VM executed the real hardware path: paired wall times were 8.3% and 5.0% lower, CPU times 8.6% and 7.3% lower and native RSS slightly lower. Full hashes, collision/fallback/guard tests passed; across this and other VM packages 333 full hashes, 28 alternate references and x86 stress checks passed. These figures are not official scoring-box or cgroup measurements. Official practice follows below; prior source is `experiments/b-crc-short/baseline.rs`.

Official CRC practice `run-a2e1d19fe55e` at `6181622001369e0bede0916b6ac20c208c840aa9` passed all gates: T=0.303478 s, M=216,702,976 bytes, S=599 and K=16.328442. The preceding no-CRC batch `run-7438a51876d1` measured T=0.305585 s, M=219,045,888 bytes, S=496 and K=16.703214; earlier no-CRC batches also varied. These separate batches show only a small wall difference, with a source-size and K cost, so the same-code repeat follows below. See `experiments/board-61816.json`.

The same-code CRC repeat `run-4757b3c43e98` at `e4ef9f3c44620b36257e25b27b3ddf58c973d6a8` passed all gates with T=0.311037 s, M=222,535,680 bytes, S=599 and K=16.043361. Two CRC batches measured 0.303478 and 0.311037 s; recent no-CRC batches included 0.301393, 0.305585, 0.309317 and 0.310730 s. These independent official batches do not establish a wall-time benefit, despite the 5–8.3% shared VM improvement. The original lookup was restored; the CRC source remains `experiments/b-crc-short/candidate.rs`. All tracks are in `experiments/board-e4ef.json`.

The restored original short-token lookup passed all official gates at `e8276cf1d60c517404eef28b909cedce5a6b293b`, run `run-1d74811ecbc5`: T=0.307437 s, M=227,622,912 bytes, S=496 and K=16.525394. The corresponding CRC batches measured 0.303478 and 0.311037 s; separate runs remain variable. See `experiments/board-e827.json`.

## Global query blocks with bounded shared bitmaps

The selected candidate indexes exact per-chunk postings and bounded phrase summaries, then lets workers claim 256-query blocks; results are sorted back into input order. Dense global bitmaps are shared through one-time initialization and an atomic 64 MiB payload cap, with exact posting fallback if reservation fails. Independent concurrency and order reviews found no defect; 323,200 reference comparisons, block-boundary and forced out-of-order tests, cap races, collision, phrase duplicates, long lines and alignment checks passed. Parent-run native x86 VM normal full-seed pairs were 2.0–2.3% faster than original baseline. On clustered expensive-query stress the dynamic candidate measured 0.0293 s versus 0.04675 s for contiguous shared-cache and 0.03464 s for original. Across this, C fused and A order packages, 314 full hashes, 28 alternate references and SIMD/concurrency/collision checks passed. VM figures are not official scoring-box or cgroup measurements; official practice follows below. The previous exact source is `experiments/b-global-queries/baseline.rs`.

The first dynamic-query practice `run-2f2167c48ddf` at `a354194892b3f2b7e4c5db6c52a6f63369fef0c2` passed all gates: T=0.302752 s, M=228,536,320 bytes, S=585 and K=16.232575. The immediately prior original-query batch `run-252f8979ebfc` measured T=0.306616 s, M=229,134,336 bytes, S=496 and K=16.525616. Separate batches show a small wall improvement and higher source count/lower K; the same code will be repeated before a conclusion. All track results are in `experiments/board-a354.json`.

The same dynamic-query source passed every official gate again in `run-0e08fded7f9c` at `df7f04789962fbc6c25504a10c964f34f6a4b658`: T=0.300329 s, M=218,513,408 bytes, S=585 and K=16.444767. Dynamic batches were 0.302752 and 0.300329 s; original-query batches included 0.306616 and 0.301393 s. Independent batches vary and do not establish a large official win, while the native x86 full and skew tests support retaining dynamic scheduling for speed. Source count and K remain worse than the original best-K batch. See `experiments/board-df7f.json`.

## Offline build-time PGO trial

This build-only trial trains the exact selected B source on sample seed 2 produced during the offline build by a byte-identical organizer generator, merges a toolchain-matched LLVM profile, and rebuilds with profile use. Only the optimized executable enters the final image; the prior non-PGO Dockerfile is `experiments/b-pgo-build18/Dockerfile.selected-before-pgo`. The [organizer rules](https://speeddemon.dev/) permit this training and exempt exact generator copies from S; build inputs are not scoring inputs and no answers are cached.

Parent-run dot VM native x86 matched Rust 1.99.1/LLVM 23.1.1 tests measured 3.7% lower wall in both paired rounds and 2.6–4.6% lower CPU with unchanged native RSS. Seventy-two full hashes, eight alternate references, natural collisions, duplicates and reference checks passed; AVX2 guard tests were run separately. This is not an official container or cgroup result. Independent source/generator/Cargo comparison, Dockerfile allowlist and shell syntax checks passed. The exact Docker build, profile matching inside that build, build time and sandbox remain unverified; a separate build host may lack the v3 instruction set and deliberately fail the CPU check. Official practice will test the reversible build, not prove hidden-data memory bounds.

The first B PGO target practice `run-062d4f86e0f5` at `261fc62` passed all gates, T=0.341621 s, M=200,306,688 bytes, S=604, K=15.614513. The previous non-PGO batches included 0.301941, 0.384857, 0.317623 and 0.301884 s with S=585. This one independent PGO batch is inconclusive given the wide variation; repeat the same B build while restoring C. See `experiments/board-261fc.json`.

The same PGO build passed all gates in `run-05ec98689ff6` at `8520cf1`: T=0.300231 s, M=222,736,384 bytes, S=604, K=16.306239. The two PGO batches were 0.341621 and 0.300231 s; the prior non-PGO batches included 0.301941, 0.384857, 0.317623 and 0.301884 s. Separate-batch target variance prevents a confident speed comparison. Native x86 paired results consistently favored PGO by 3.7%; provisionally retain it for speed and repeat the same build before final selection. See `experiments/board-8520.json`.

A third identical PGO build passed all gates at `f4d2a86`, `run-0bd11b42a49d`: T=0.290780 s, M=226,164,736 bytes, S=604 and K=16.518574. Three PGO batches are 0.341621, 0.300231 and 0.290780 s; preceding non-PGO batches included 0.301941, 0.384857, 0.317623 and 0.301884 s. The two faster PGO practices and consistent 3.7% paired native x86 improvement support retaining PGO under the speed-first objective, but independent target batches are noisy and do not establish a precise speedup or hidden-data cgroup maximum. See `experiments/board-f4d2.json`.

## Guarded medium-token CRC with PGO

This single-source trial builds a query-derived table for 9–16-byte terms, hashes both normalized words with hardware CRC32C, and compares both full words before returning an ID. It discards the table and retains the original generic lookup if insertion probes exceed 32 or any cyclic occupied run exceeds 64; other lengths and non-SSE4.2 targets keep their existing paths. The thresholds bound trial insertion and accepted run length, not allocation or original fallback's worst-case collisions. Exact previous source is `experiments/b-medium-crc26/baseline.rs` and the existing offline PGO Dockerfile is unchanged.

Independent reviews found no concrete defect. Portable properties exercised normal and forced collisions, wraparound, 96,874 case/padding/alignment inputs, 300,000 CRC pairs, threshold boundaries, 80 mixed reference corpora, long/sharded records and 250,000-document duplicate-phrase stress. Parent-run x86 dot VM tests compared separately trained, matched Rust/LLVM PGO builds on seed-2 sample data; candidate wall was 9.8% and 8.5% lower and CPU 7.6% and 8.3% lower in paired batches, with median native RSS about 1–2% higher. Across this and D window, 216 full hashes, alternate references, actual SSE4.2/AVX2 protected-page tests, natural collision fallback and queue-oracle checks passed. These are native measurements, not official cgroup or hidden-data proof. Official single-change practice follows.

The first CRC+PGO official practice `run-4409c94d089f` at `ab28d6a` passed all gates: T=0.299154 s, parent-cgroup M=214,007,808 bytes, S=750, K=15.940532. Recent PGO baseline batches were 0.290780, 0.294090 and 0.293197 s with S=604; separate runs vary, and this first candidate batch does not reproduce the paired dot VM gain. The increased S reduces K. Repeat exact candidate before deciding under the speed-first objective; see `experiments/board-ab28.json`.

The same CRC+PGO source passed all gates again at `e196f1f`, `run-d6c4bff5e5da`, T=0.346498 s, M=195,661,824 bytes, S=750, K=15.079418. Its target batches of 0.299154 and 0.346498 s did not beat recent baseline PGO batches 0.290780, 0.294090 and 0.293197 s, despite the VM matched-PGO paired improvement; other tracks also varied, so the target batches are not a controlled pair. Restore the exact prior B source for a further single-variable target comparison. CRC remains available as a tested experiment. See `experiments/board-e196.json`.

The restored baseline PGO build passed all official gates at `8001800`, `run-1e974d4576e2`: T=0.295238 s, M=225,869,824 bytes, S=604, K=16.397666. The previous CRC+PGO batches measured 0.299154 and 0.346498 s at S=750; this independent baseline run and earlier 0.290780–0.294090 s baseline batches support retaining the original source for target speed and score, while the matched native VM CRC gain remains documented. Separate official batches vary; no precise causal speedup is established. See `experiments/board-800180.json`.

## Merge of speed-opt source (2026-10-31)

`src/main.rs` replaced with the `speed-opt` version (Dockerfile, .speed-demon.toml and build flags unchanged). Sandbox A/B against `3b1126e` on full seed 1 (2-core arm64, noisy, min of alternating runs, hashes match): no official board run yet for this source. Add the run ID here once the board has scored it, and revert to `3b1126e` if the board T is not better.
Sandbox CPU min: 3.95 s -> 1.92 s.

## Round 2 trial: global bitmaps + 16-bit postings (2026-10-31)

Board `run-225241b20c9f` at `ccbfbc0`: T=0.381388 s, M=76.1 MB, S=496, K=18.47, below v23 (K 19.6). Memory halved but time rose; v23 source restored.

Round-3 trial (c2): queries answered once over doc-aligned chunks claimed dynamically; shared bitmaps for frequent terms, per-chunk 16-bit postings otherwise; list terms renumbered first (16-bit token stream); 16-byte inline-key hash slots; AVX2 movemask tokenizer; prefetched phrase anchors; df-based sampling; exit right after write. Local: CPU -22%, heap 113 -> 55 MB, S 387 -> 619.

## Linux sandbox profile of current source (local sandbox measurements, not official scores)

`experiments/b-linux-profile/` profiles `src/main.rs` at `dddc0ea` (SHA-256 `6607a94c...`, unchanged) on full seed 1 in an 8-vCPU Xeon Platinum 8488C sandbox (4 cores x 2 SMT, rustc 1.92.0, x86-64-v3, no PGO); every run matched the published hash. The uninstrumented binary measured median wall 0.227 s, CPU 1.539 s and max RSS 65,876 KiB at 8 threads. Instrumented main was 224.5 ms: index scan 172.5 ms (76.8%), answer 27.8 ms (12.4%, 98% Boolean), and about 25 ms serial at every thread count, of which query parse/intern is 15.4 ms. Inside the scan, slot lookup is 34.9% and tokenize/mask 30.8% of time, and 20.8% of tokens are not query terms; 6 threads produce 18 chunks and a 68.6 ms idle tail, while 12 threads would give 24 chunks (unmeasured). These are local sandbox measurements, not official scores and not board run results; see `experiments/b-linux-profile/README.md` for tables, ranked bottlenecks, caveats and reproduction commands.

## Query-term filter and presized intern table (local sandbox measurements, not official scores)

This candidate adds two changes to `src/main.rs` at `dddc0ea`. First, a 1<<20-bit (128 KiB) filter keyed on the existing 24-bit `Plan::hash`, built after interning: a short token whose bit is clear is looked up as the empty key at a known empty slot, which matches at once instead of probing the 3.15 MB table; false positives take the normal probe, so correctness does not depend on the filter. Second, the intern table is presized to `(qtext.len() / 16 | 64).next_power_of_two()` slots (131,072 on seed 1) instead of growing from 4,096 by rehash; the `| 64` keeps tiny query files from getting a full 2-slot table. A parallel query parse, prefetching during intern and a more compact filter form were measured and dropped. S 620 -> 634 (+2.26%, break-even wall gain about 0.68%), raw lines 631 -> 652.

In the 8-vCPU Xeon 8488C sandbox (rustc 1.92.0, x86-64-v3, no PGO), 21 interleaved pairs against the `dddc0ea` binary gave median paired wall -4.59% (19/21 wins) and CPU -3.96% at 8 threads, -3.51% (21/21) at 6 threads and -2.83% (16/21) at 12 oversubscribed threads, with max RSS within 1.5% at 6 and 8 threads. The filter alone gave -2.95%; the presize alone was within noise on wall (-1.38%, +0.20%) but cut serial parse/intern from 14.8 to 16.0 ms to 12.6 to 14.0 ms for 0 S lines. Every run matched the seed-1 hash `f86973c2...0927`, and generated tiny/sample seeds plus edge fixtures match the official reference (pass=34, with the two pre-existing no-trailing-LF `docs.txt` failures unchanged). These are local sandbox measurements, not official scores; see `experiments/b-filter-parse/README.md` for sources, SHA-256s, reports and reproduction commands.

Official board run: pending (run ID to be added after the board run).

## Leaner source with equal speed (local sandbox measurements, not official scores)

This candidate rewrites `src/main.rs` at `8de6f94` to cut S without changing the algorithm, prefetching or thresholds. Most of the drop comes from statements that rustfmt expanded heavily (long chains, long `if` expressions and tuples), now written as short statements with the same operations. Two pieces of serial bookkeeping are simpler with the same values: the document count reads the last line via `rsplit` (13 -> 2 S lines), and phrase hits are sorted and deduplicated once as (query, id) and sliced with `partition_point`, instead of a stable sort, an offset table and a per-query copy and dedup. A shared `sorted_line` helper prints both list results; two `boolean()` arms merge. Removing the anchor prefetch passes (+2.15% and +3.10% with one level kept), deduplicating list terms in the scan callback (+2.83%, +1.8 MB RSS), dropping the slot prefetch (neutral, 1 line) and token instead of document frequency in the sample (neutral, changes the plan) were measured and rejected. S 634 -> 567 (-10.6%, about +1.7% K at S^-0.15, worth about 3.4% wall), raw lines 652 -> 674.

In the 8-vCPU Xeon 8488C sandbox (rustc 1.92.0, x86-64-v3, no PGO), 21 interleaved pairs against the `8de6f94` binary gave median paired wall -2.01% (16/21 wins) and CPU -1.55% at 8 threads, and -1.61% (18/21) at 6 threads, with max RSS equal within noise. A first version briefly used a `(u32, usize)` frequency vector (+0.6 MB touched); it was typed `(u32, u32)` before these runs. Every run matched the seed-1 hash `f86973c2...0927`, and generated tiny/sample seeds plus edge fixtures match the official reference at default, 1 and 12 threads (pass=34, with the two pre-existing no-trailing-LF `docs.txt` failures unchanged). These are local sandbox measurements, not official scores; see `experiments/b-lean/README.md` for sources, SHA-256s, reports and reproduction commands.

Official board run: pending (run ID to be added after the board run).

## Branch-free scan writes, cheaper token key, tokenized flat query parse (local sandbox measurements, not official scores)

This candidate changes `src/main.rs` at `a6a2151` in five steps picked from a re-profile at 8 threads (scan masks 45%, callback 22%, lookup 19% of scan time; serial 22 ms, 12.8 ms of it query parse/intern). The bitmap group write in the scan callback no longer branches on whether a token is a bitmap term: `group` has one spare word that all other terms write into (callback 18.7 to about 10 cycles per token). The query-term filter select became a mask instead of a compiled branch. `key()` masks the 16 loaded bytes with a window of a 32-byte constant instead of a per-half u128 shift (masks part 35.6 to 30.8 cycles per token). The 64-byte token loop moved into `each_token`, which the query parse now uses as well (terms are lowercase per spec, so `B`/`P` start a query and `A`/`O`/`N` are operators), and all query terms live in one flat `Vec` with per-query offsets instead of a `Vec` per query, which removes `enum Query` and `remap`; parse/intern 13.4 to 8.1 ms, max RSS about 2 MB lower. More or fewer chunks per thread, other bitmap spill thresholds, frequency-ordered table reinsertion, other key mask forms and a branch-free CSR dedup were measured and rejected. S 567 -> 558 (-1.6%), raw lines 674 -> 672.

In the 8-vCPU Xeon 8488C sandbox (rustc 1.92.0, x86-64-v3, no PGO), 21 interleaved pairs against the `a6a2151` binary gave median paired wall -14.16% (21/21 wins) and CPU -13.12% at 8 threads (179.0 vs 208.1 ms), -21.82% (21/21) at 6 threads and -13.91% (21/21) at 12 oversubscribed threads, with median max RSS 62,632 vs 64,796 KiB at 8 threads. Every run matched the seed-1 hash `f86973c2...0927`, and generated tiny/sample seeds plus edge fixtures match the official reference at default, 1 and 12 threads (pass=34, with the two pre-existing no-trailing-LF `docs.txt` failures unchanged); the portable x86-64 build also passes. These are local sandbox measurements, not official scores; see `experiments/b-speed3/README.md` for sources, SHA-256s, reports and reproduction commands.

Official board run: pending (run ID to be added after the board run).
