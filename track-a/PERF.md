# Performance and correctness log

Earlier iteration timings below are local; the first official practice run is recorded at the end.

- Replaced general timestamp parsing and per-line split with direct fixed-field parsing, endpoint interning, and a compact collection of uint32 latencies per hour and endpoint. All latencies are retained; exact percentiles are obtained by sorting each group. This is the initial candidate, not a measured comparison of individual optimizations.
- Official generator seed 1, full: input SHA-256 `7ec80ba45bceef51ac7f79d3a14521fc6187b2dcb87b5e5542d08063fe5d962a`; output SHA-256 `495ca09682b9673ef836a506496177680bb4a3af54255174befddb1f83481cd3`, matching the published expected digest. Five consecutive native runs took 0.496, 0.411, 0.553, 0.411 and 0.411 seconds on this Mac, with peak child RSS 26,689,536 bytes. Other processes were active; these are not official measurements, and Linux cgroup memory accounting may differ.
- Official generator seed 999, sample: candidate and official reference both produced SHA-256 `04168fcd480940157d8221e2ce79e49a3e8f41d4c66cbc3634edd1cb5c91c242`.
- Independent synthetic differential checks passed empty input and 1,000, 100,000 and 100,000 records on different seeds, including day/month boundaries, duplicates, methods, uint32 extremes, statuses 499/500/599 and endpoint byte ordering.
- Official generator seed 1, tiny: output SHA-256 `c24fa507c963eaeac9224fd8435019b4f4e8c002ece7e32f316681a3957eb92f`, matching the published digest.

## Local comparison: chunked parsing and percentile selection

The original full-sort/line-reader baseline is preserved at `track-a-agent/main.cpp` in this workspace. We compared it with selection alone, 1 MiB chunked reads alone, and both together on the official seed-1 full dataset. Eight runs of each variant were rotated across positions, every output was hashed, and the lowest and highest times for each variant were discarded. Other agents were running concurrently, so these are exploratory Mac timings, not a controlled or official ranking. Middle-six means: baseline 0.380 s, selection only 0.381 s, chunking only 0.269 s, combined 0.256 s. All 32 runs produced the published full hash. The initial selection-only comparison was noisy, so selection's benefit on the scoring CPU is still unproven.

Final code passed the tiny published hash and matched the official reference on sample seed 999. It also passed the synthetic differential tests described above. The parser keeps partial lines between reads and handles empty input; percentile selection retains exact nearest ranks.

This historical comparison used C++ candidates; the final C++ source is preserved at `experiments/prev-candidates/track-a/main.cpp`. From the workspace root, rebuild the preserved baseline and final candidate with the same local compiler and run a paired, alternating comparison:

```sh
c++ -O3 -std=c++17 -o /tmp/track-a-baseline track-a-agent/main.cpp
c++ -O3 -std=c++17 -o /tmp/track-a-final experiments/prev-candidates/track-a/main.cpp
python3 official/generators/a_ingest.py --seed 1 --scale full --out /tmp/speed-demon-a-full
python3 - <<'PYBENCH'
import hashlib, subprocess, time
expected = "495ca09682b9673ef836a506496177680bb4a3af54255174befddb1f83481cd3"
times = {name: [] for name in ("baseline", "final")}
for i in range(8):
    order = ("baseline", "final") if i % 2 == 0 else ("final", "baseline")
    for name in order:
        start = time.perf_counter()
        subprocess.run([f"/tmp/track-a-{name}", "/tmp/speed-demon-a-full/requests.log", "/tmp/track-a-output.txt"], check=True)
        times[name].append(time.perf_counter() - start)
        with open("/tmp/track-a-output.txt", "rb") as f:
            assert hashlib.file_digest(f, "sha256").hexdigest() == expected
for name, samples in times.items():
    print(name, samples, "middle-six mean", sum(sorted(samples)[1:-1]) / 6)
PYBENCH
INGEST_BINARY=/tmp/track-a-final python3 experiments/a-verification/test.py
```

Re-run this comparison when the machine is otherwise idle, then profile and validate again in the official Linux container. This does not substitute for live-board run IDs.

Additional generator sample seeds 2 and 98 matched the official reference byte for byte: seed 2 `fd26778fa5e70fac2905a0a0f0142bd26ca4e6f510dfe182a881e525286ff12f`; seed 98 `50d8b76cb16a56df1aaa017a843ee615d5d198fd43eda73bc45b3df768969df2`.

## Controlled local comparison

Five interleaved full-data pairs after warmup on macOS ARM: original median 0.365936 s, current median 0.244733 s (1.50×). Every output matched the full hash. Also passed nine deliberately positioned 1 MiB chunk boundaries. Details: `experiments/bench-a.json` and `experiments/a_chunk_boundaries.py`. These are local measurements, not board scores.

## Native x86 dot VM

The candidate and original were tested on the full seed-1 dataset with GCC 14. See `experiments/dot-vm.md` for the five-run medians and limitations. This was not a board run.


## Three-shard native x86 follow-up

The then-selected insertion-based three-shard buffered implementation had a 0.200 s median and 36.0 MiB peak RSS versus 0.386 s and 25.2 MiB for the prior selected source on a shared native x86 VM. With pinned clang-format 23.1.3 and scc 4.1.0 on temporary source and Dockerfile copies, code-line counts were 226 versus 127; applying those time, memory and source factors gives approximately 1.187× K before dependency effects. This is an estimate, not an official score; the official cgroup peak and trimmed timing may differ. The prior source is `experiments/a-serial-f45.cpp`.

GCC 14 warns in the vector range-insert that merges independent shard groups. Under the input contract, the two vectors cannot alias and their combined length is bounded by the 3.1 million records; supplied x86 ASan/UBSan, full hashes, reference and boundary checks found no defect. That strongly suggests a false positive but does not prove a compiler bug. A separately tested checked resize-and-copy alternative suppresses the diagnostic, including with `-Werror=stringop-overflow`, and passes restricted ARM Linux GCC 14 and allowlisted GCC 15 full hashes; At that point its x86 speed and source scoring were not yet known; see the later checked merge follow-up below. See `experiments/a-three-shard-checked.cpp` and `experiments/bench-a-merge-check.json`.

That insertion-based candidate passed the official offline restricted ARM Docker full hash in 0.56 s including startup, 16 exact shard-boundary cases, nine 1 MiB boundaries, four synthetic datasets, and fresh sample reference comparisons. No official board run ID is claimed.


## Checked merge follow-up

The selected merge now checks vector capacity before resizing and copying the nonempty source. This removes the GCC 14 `-Wstringop-overflow` warning. The prior insertion-based code is `experiments/a-three-shard-insert.cpp`. On a shared native x86 VM, checked measured median 0.2124 s / peak RSS 36.07 MiB versus insertion 0.2161 s / 35.84 MiB. Pinned clang-format 23.1.3 and scc 4.1.0 counted 233 versus 226 code lines including Dockerfile. The resulting estimated K ratio is 1.0028 assuming equal dependency factors, too small to distinguish from noise; the checked merge was chosen for explicit bounds and diagnostic clarity, not a claimed speed gain. See `experiments/static-a-checked/` and `experiments/dot-vm.md`.

The x86 full hash, five alternate references, 25 boundary cases, four synthetic cases and ASan/UBSan passed. Independently, the selected checked code passed the restricted ARM Docker full hash in 0.70 s including startup, seed-999 sample against the reference, 16 shard boundaries, nine read boundaries, and four synthetic cases. The checked version has not yet been run on the board; the earlier f45 baseline run is recorded below.


## First official live-board practice run

The public seed-1 practice run at commit `f45c4cf3f707123e705b930c6b1f08b8facefdc5` is `run-55a9d9b7e7df`. It passed the check, build, correctness, timeout and sandbox gates. The board reports T=0.475183 s, M=35717120 bytes, S=127, D=1, K=10.522722 and 51.106405 machine points. This is a single live-board run, not the final five-run hidden-seed score. Source and snapshot: `experiments/board-f45.json`. This measured the earlier f45 serial candidate, not the later local three-shard or checked-merge changes.


## Live-board practice run at 664ba1a

Run `run-f2cc9af47d9d` at commit `664ba1aafb0d765427f49d5ad933b6c1a18b0f24` passed check, build, correctness, timeout and sandbox. The board reports T=0.226277 s, M=47616000 bytes, S=233, D=1, K=13.144081 and 55.936511 machine points. This single public-seed practice run is not final hidden-seed scoring. See `experiments/board-664.json`.


## Live-board practice run at 2fc9110

Run `run-0739ec66c62d` at commit `2fc9110d0c2acfc880350efbc240f5aa4620bd99` passed check, build, correctness, timeout and sandbox. The board reports T=0.227481 s, M=47534080 bytes, S=233, D=1, K=13.113766 and 55.886371 machine points. This is a single public-seed practice run, not final hidden-seed scoring. See `experiments/board-2fc.json`.


## Selective Rust candidate at PR head f348fd7

In five alternating full seed-1 pairs on the shared dot x86 VM, the Rust candidate had a 0.0516 s median versus 0.1813 s for the C++ source at 02d7b4c. All outputs matched. This is native process timing, not official board scoring or cgroup memory. The source has no third-party dependencies. Its source score and official runtime and memory have not yet been measured.

Independent ARM macOS testing used a temporary source copy with only the Linux anonymous mmap flag changed for Darwin. It matched the full seed-1 output hash, the independent zero/1k/100k/100k oracle suite, 16 six-way shard split checks, nine 1 MiB boundary checks, and 84 page-end/reference combinations. The live-board run IDs above belong to earlier C++ implementations, not this candidate.

The unchanged Linux candidate subsequently matched the published full seed-1 SHA-256 in a restricted offline ARM Linux container.

Official public-seed practice run `run-b4c4f652f111` at commit `89795bbc852b5e24e9f976c7291b3c3a21101361` passed all gates: T=0.047542 s, M=48,148,480 bytes, S=273, K=27.939894. The prior C++ run at 02d7b4c had K=13.101162. These are separate practice measurements, not final holdout results. See `experiments/board-897.json`.

## Six-worker default

The current candidate caps the default at six available workers, while preserving the `SD_THREADS` override. On the shared dot VM, native x86 medians were 0.0428 s with six, 0.0462 s with the nine-worker default on that VM, and 0.0566 s with twelve. These are not official scoring-box measurements; the official runner may expose a different CPU count and the cgroup peak and K must be measured on the board. The previous source is `experiments/a-worker-baseline-15c/main.rs`.

A temporary Darwin-adapted build matched the full seed-1 hash at default and forced one and twelve workers, the synthetic oracle suite including empty and two 100,000-record datasets, 14 page-edge sizes at six worker counts, and the 132,624-group latency grid at five worker counts. The Linux candidate differs only in its default cap; the local Docker socket was unavailable, so the official build and sandbox gates must validate the Linux image. At 15c6be0, prior A run `run-7373c45a5aaf` passed all gates and reported T=0.047562 s, M=50,741,248 bytes, S=273, K=27.642525 (`experiments/board-15c.json`).

Official practice `run-39ea5704e350` at b9c2b54 passed every gate, with six workers T=0.050492 s, M=41,328,640 bytes, S=273, K=27.952360 (`experiments/board-b9.json`). The previous auto-worker practice measured 0.047562 s. Since the objective is wall speed, auto workers have been restored for a further comparison; the tested six-worker version is `experiments/a-six-b9/main.rs`. The separate runs are subject to noise.

The restored auto default passed all gates in official practice `run-2ff15013ed39` at e8e828a: T=0.051316 s, M=50,696,192 bytes, S=273, K=26.616965 (`experiments/board-e8.json`). Auto's two results bracket the six-worker result, so separate practice runs do not establish a reliable ordering.

`experiments/a-verification/latency_grid_test.py` additionally checked 132,624 singleton groups across all 72 hours and 1,842 endpoints, random unsigned-32-bit latencies of every decimal width, 0 and 4294967295, and 1, 2, 6, 12 and 64 workers. This used the same Darwin-only test adaptation.

## Proposed hardened PR line reduction

The isolated merge candidate adapts PR 385a930 with dynamic endpoint-table growth, exact-byte collision comparison, explicit SWAR wrapping and a guard before tail shifts. Its full seed-1 hash, 5,020-endpoint forced-collision/growth cases, page boundaries, latency grid and overflow-check-enabled synthetic suite passed using a temporary Darwin mmap flag adjustment. On the shared x86 dot VM it measured 0.05938 s versus 0.05436 s for the existing source. The speed-first merge retains the existing implementation; the tested rewrite is `experiments/pr1-c634/trimmed-a-hardened.rs`. These are native VM observations, not official scores.

## Optional prefault ablation

The selected A source removes the per-shard `MADV_POPULATE_READ` hint; parsing and output are unchanged. The previous source is `experiments/a-ablation/baseline-linux.rs`. On the shared native x86 dot VM the no-hint variant was 14.1–21.6% faster across warm-cache comparisons with similar process RSS. Cold-cache performance was not established. The [official scoring harness](https://github.com/hackathon-raptors/speed-demon-2026/blob/ad1f06063a76bf94066f169e133ec0c2e1485b65/harness/README.md) warms the dataset into the page cache before timing. Native VM and official cgroup results are distinct.

The exact no-hint candidate, with only the anonymous-map flag adapted for Darwin, passed the full seed-1 hash, 14 page-edge sizes at six worker counts, the 132,624-group latency grid at five worker counts, the independent 0/1,000/100,000/100,000-record synthetic oracle, and 1,803 adversarial endpoints at six worker counts against the official reference. These checks do not execute Linux memory-advice behavior.

Official public-seed practice at `82b8d8154f4a7455e9944f0e43314ffcacb50c81`, run `run-41af60a57593`, passed all gates: T=0.041663 s, M=51,466,240 bytes, S=273, D=1, K=29.451013. The immediately preceding unchanged-advice run `run-6b1aed9cba62` measured 0.049512 s and M=50,577,408 bytes, the new run was approximately 15.9% faster in this separate comparison. These are individual official practice batches, not a controlled paired trial or final hidden-seed result; further repetitions may vary. All four track results and run IDs are in `experiments/board-82b8.json`.

A same-code repeat at `2f96e72ceea30a56d283477e6ae3815b45c138bf`, `run-90c60a4f060b`, passed all gates with T=0.051520 s, M=46,694,400 bytes, S=273 and K=27.004685. This varies materially from the first no-hint practice result of 0.041663 s and is slower than the immediately preceding hint baseline of 0.049512 s. Therefore these official batches do not establish a stable speed improvement. The independently reported warm native x86 VM speedup remains evidence but is not an official result. All track run IDs are in `experiments/board-2f96.json`.

## Compact records with exact escapes

The selected candidate stores a record in 32 bits when its local endpoint ID fits 11 bits and latency is below 1,048,575; otherwise it emits an escape and preserves the original 64-bit record in order. Both summary passes independently consume the same escape sequence. Independent review, forced-collision/growth tests, 49,440 encoding properties, synthetic and page-boundary references, a 132,624-group latency grid, 2,422 endpoints and all-escape/alternating stresses passed. Parent-run shared native x86 VM paired full-data runs were 4.0–13.6% faster with 4.4% lower native RSS. A full-size all-escape stress was 11.6–13.1% slower with 6.5% higher native RSS; all-escape payload grows from 8 to 12 bytes per record, before allocation overhead. Across this and C owner work, 276 full hashes, 16 full-size all-escape runs, 20 alternates, collision/fallback/guard checks passed. These are not official scoring-box or cgroup results. The prior exact source is `experiments/a-compact-records/baseline.rs`; official practice follows below.

The first compact-record practice `run-9c1267f323f8` at `f78670e1d23a53dcd71567f0e883ebddd95e2cfb` passed all gates: T=0.042319 s, M=38,760,448 bytes, S=303 and K=30.446862. The immediately preceding baseline batch `run-4d223e0cd1f5` was T=0.041038 s, M=50,163,712 bytes, S=273 and K=29.826959. Separate-batch wall times are close while the compact version used less cgroup peak memory; the same-code repeat follows below. All track results are in `experiments/board-f786.json`.

The same compact-record source passed all gates in `run-bc5af008533c` at `e89591928fbfc15db9a303335915a36c86869a47`: T=0.040773 s, M=38,969,344 bytes, S=303, K=30.985396. The two compact batches measured 0.042319 and 0.040773 s; the preceding no-compact batch measured 0.041038 s with M=50,163,712 bytes and S=273. Separate batch timing is variable, but lower cgroup memory and VM speed evidence support retaining the candidate; all-escape costs remain documented above. See `experiments/board-e895.json`.

## Bounded CRC32C endpoint hashing

This trial uses hardware CRC32C for endpoint-word hashing only when the build target guarantees SSE4.2, retaining exact endpoint byte comparison. A fast shard that exceeds 48 occupied probes during lookup or rehash is dropped and parsed again with the original hash; no partial output is emitted. Successful shards rebuild their unique endpoint table with the original canonical hash in original ID order so compact and escaped record IDs remain stable across shard merges. Other architectures retain the original parser. The exact prior source is `experiments/a-crc-bounded15/baseline.rs`; the fast-path probe limit does not provide a worst-case bound for the original fallback hash table.

Independent review, canonical-hash and ID-rebuild properties, simulated collision/restart and mixed-shard checks passed. Parent-run native x86 dot VM testing exercised actual SSE4.2, guarded pages and forced fallback; twelve-worker full-seed pairs were 2.0–5.7% faster, nine-worker results mixed, and native process RSS unchanged. An initial all-escape slowdown did not reproduce. Across the A, B and D packages, 308 full hashes, 28 alternate references and 48 all-escape executions passed along with actual ISA/guard/fallback tests. These are native VM results, not official scoring-box or cgroup measurements. The immediately prior unmodified A official practice `run-4bb24a2fc644` at `bce4da4e936059748493efd8b03b339902ce7489` passed every gate at T=0.039555 s, M=35,418,112 bytes, S=303, K=32.065811. The exact candidate is being sent for single-change official practice.

Official practice `5e32c97`, bounded CRC candidate: run `run-930371a77434`, all gates passed, T=0.039919 s, parent cgroup peak 37,974,016 B, S=434, K=29.825917. Prior unmodified A at `bce4da4` was 0.039555 s, peak 35,418,112 B, S=303, K=32.065811. These independent runs do not establish a CRC speed win; dot VM paired 12-worker trials were 2–5.7% faster, with mixed 9-worker results. Repeat same source before deciding; see `experiments/board-5e32.json`.

The same CRC source passed all gates again at `a4e80b3`, `run-7304769756fc`: T=0.042049 s, M=38,752,256 bytes, S=434, K=28.943010. Its two official batches (0.039919 and 0.042049 s) overlap previous compact baseline batches (0.039555, 0.040773, 0.042319 s), with no established target speed improvement and higher S. The simpler exact prior source is restored for a further single-change target comparison; CRC is retained as an experiment, not discarded evidence. See `experiments/board-a4e80.json`.

The restored original hash passed the official practice at `c0a5426`, `run-9eea61ec9051`, T=0.041768 s, M=38,920,192 bytes, S=303, K=30.621832. This is within the range of both previous baseline and CRC batches; these independent batches do not establish a wall-time difference. Retain the simpler baseline while CRC remains available for future target testing. Full run IDs are in `experiments/board-c0a5426.json`.

## Board trial: speed-opt source (2026-10-31)

`src/main.rs` replaced with the shorter `speed-opt` version (Dockerfile and config unchanged); hash verified at 1, 2 and 12 threads on full seed 1. Compare against the prior best `2d67ab5` (`run-142f6588f59d`, T=0.038664 s, M=32.2 MB, S=303, K=33.07) and revert if K is lower.
Result: `run-a94603610d79` at `ea12ae5`: T=0.052896 s, M=32.9 MB, S=188, K=30.23. Slower on the box despite fewer lines, so the `2d67ab5` source is restored.
Round 2 at `ccbfbc0`, `run-4a52a83d2464`: per-thread MADV_DONTNEED on each chunk, sharded shared endpoint maps with their own name copies (no merge, no re-reading dropped pages), hourly records freed after summarising. T=0.034982 s, M=22.3 MB, S=310, K=37.26 (prior best 33.07). Kept.

Hash-only trial: endpoint identity by 64-bit hash plus length, no byte compare (collision odds ~1e-13 per dataset); compare against `a571dce` (K 37.34).
Result: `run-93607a10da06` at `a9f6ae3`: T=0.037754 s, M=23.2 MB, S=299, K=35.78, below `a571dce` (37.34); exact byte compare restored.
Result: `run-ab14ebe4067b` at `feadbcc`: T=0.038692 s, S=316, K=35.62; fixed split ran 0.0348-0.0352 s in 3 of 4 runs, so reverted.

## Compact endpoint table (local x86 VM, branch a-x86-speed)

Each thread's endpoint table now keeps its own compact arena of entries (hash, length, shared id, then the name bytes), so a probe reads one slot and one arena entry and the exact byte compare no longer reaches back to the endpoint's first occurrence in the mapped file. Shared ids are dense (one atomic counter, the 16 sharded maps kept), stored in the entry, so the `ids` indirection is gone. With `target-cpu=x86-64-v3` the space after the endpoint is found with one 64-byte AVX2 compare (word-at-a-time fallback past 64 bytes), the hash uses only the first, middle and last words plus length, and names under 64 bytes are compared with one masked AVX2 compare; other targets use a portable fallback of the same masks. Over-reads stay within the 4 KiB zero pad of `map_file` and the arena's 64-byte zero tail. Exact byte comparison is retained; more than 2,047 endpoints still escape to 64-bit records.

Local x86 VM paired medians (61 rounds each, two invocations with shuffle seeds 31 and 32) against the prior source `experiments/a-x86-speed/baseline.rs`: 0.8514 and 0.8536 at 8 threads, 0.8414 and 0.8409 at 12. Parse phase 26.7 ms to about 22 ms at 8 threads. Passed `experiments/a-x86-speed/check.py` (full hash at 1, 2, 3, 6, 8, 12 threads and default, the three verification scripts, sample seeds 2, 98, 999, 4242) and `adversarial.py` on AVX2, forced-collision and scalar builds. These are not official scores. Details and rejected steps: `experiments/a-x86-speed/README.md`.

Follow-up on the same branch: the hour now comes from one 8-byte load of `MM-DDTHH` with nibble arithmetic, and endpoints of 64 to 127 bytes use a second 64-byte AVX2 scan and masked compare instead of a word loop and `memcmp`. Local x86 VM paired medians against the previous source (81 rounds, two invocations): 0.9784 and 0.9842 at 8 threads, 0.9861 and 0.9904 at 12. Cumulative against the branch-point source (41 rounds): 0.8494 at 8 threads, 0.8303 at 12. Same correctness evidence as above. Rejected parse candidates (single shared map, atomic ids alone, dynamic ranges, two-word hash, push trims) are in `experiments/a-x86-speed/README.md`. Not official scores.

## Local x86 VM speed pass (a-x86-speed)

Summary phase, scheduling and build work on branch `a-x86-speed`, after the parse changes above. The parse threads now go on to summarize: they meet at a `Barrier`, one sorts the names and regroups the records by hour, and after a second barrier all take hours from the queue, so no second thread set is spawned. The summary lays each hour's groups out in rank order but indexes them by endpoint id (no `rank[id]` lookups), packs count and 5xx count into one `u64` per id, reuses the per-worker buffers across hours and formats numbers with a two-digit table into one line buffer. Groups of up to 64 values (most groups; the median group has 5 records) get their three nearest-rank percentiles from branch-free AVX2 rank counting: the value of rank r is the largest value with at most r values below it, so every value's count of smaller values replaces a sort. Larger groups and non-AVX2 builds keep `select_nth_unstable`. The endpoint hash now uses only the first and last words and the length with one multiply (the FEAT-002 near-miss `p6b`, kept in combination). The exact byte compare and the 64-bit escapes for ids above 2,047 or large latencies are unchanged.

Local x86 VM measurements only (shared 8 vCPU Xeon Platinum 8488C KVM VM, 4 cores x 2 hyperthreads, not the i5-13500 scoring box; no board run was made for this source and no official score is claimed). Paired medians candidate/baseline, 41 interleaved rounds per invocation:

| Change | 8 threads | 12 threads | Verdict |
|---|---:|---:|---|
| id-indexed groups, packed counts, buffer reuse, table formatting (`s1`) | 0.9876, 0.9948 | 0.9777, 0.9968 | folded into the kept bundle |
| plus AVX2 small-group rank counting (`s1e`, vs `s1`) | 0.9775, 0.9575 | 0.9802, 0.9644 | folded |
| plus parse threads reused for the summary (`s2b`, vs `s1e`) | 0.9954, 0.9675 | 1.0008, 0.9839 | folded; removing it from the bundle costs 1.0242 / 1.0061 |
| bundle plus two-word hash (`s2c`) against the previous production source | 0.9319, 0.9341 | 0.9420, 0.9259 | **kept** |
| lines written straight into reused output buffers (`s3a`/`s3b`) | 1.0101, 1.0266 (vs `s2b`); 0.9829, 1.0104 (vs `s2c`) | 0.9900, 1.0071; 1.0237, 0.9980 | rejected |
| parse-side per-hour id counts (21 rounds) | 1.0112 | 1.0239 | rejected |
| output buffer pool alone (21 rounds) | 0.9709 (earlier screen 1.0003) | 1.0017 | rejected, did not reproduce |
| full sort up to 64 values (21 rounds) | 1.0084 | 1.0231 | rejected |
| leaking records instead of freeing (21 rounds) | 1.0057 | 1.0020 | rejected |
| largest hours first (21 rounds, vs `s1e`) | 1.0947 | 1.0375 | rejected (the in-order writer then runs as a serial tail) |
| static glibc linking (`+crt-static`) | not measured | not measured | not applied: this host has no `libc.a` and cannot reach package repositories; the Dockerfile build was not run locally |

Empty-input wall time (startup and exit, 300 rounds, includes about 0.92 ms of Python spawn cost measured with `/bin/true`): previous source 1.82 ms, new source 1.63 ms. Cumulative against the branch-point source `experiments/a-x86-speed/baseline.rs` (41 rounds, seed 501, every output hash verified): paired median 0.7848 at 8 threads (0.0379 s to 0.0296 s median wall), 0.7790 at 12 threads (0.0468 s to 0.0365 s) and 0.7800 at the default thread count (0.0377 s to 0.0294 s). These are local x86 VM numbers, not official scores.

Correctness: `experiments/a-x86-speed/check.py` on the cargo build (full seed-1 SHA-256 `495ca09682b9673ef836a506496177680bb4a3af54255174befddb1f83481cd3` at `SD_THREADS` 1, 2, 3, 6, 8, 12 and default, `test.py`, `page_end_test.py`, `latency_grid_test.py`, sample seeds 2, 98, 999 and 4242 byte-identical to the official reference); `adversarial.py` at 1, 2, 3, 7 and 12 threads on the AVX2 build, a scalar build (also the full hash) and a forced-constant-hash build (`--quick`), including a new case with groups of every size 1 to 200 whose latencies are tied, equal, around 2^31 and 2^32 - 1 or spread over 32 bits; the full hash at 73 and 100 threads. Source SHA-256 of the new `track-a/src/main.rs`: `12589c3dfc134a6c45d8af28aa9470bdcfea2a0b2a54fbe3838eb29010b2ad6e`. Raw samples, variant sources and rejected candidates: `experiments/a-x86-speed/README.md`.


## Current-hour record cursor (local x86 VM, branch a-x86-speed-3)

A parse breakdown of the post-PR #4 source (8 threads) put about 10 ms of the 20 ms parse in walking the bytes, about 4 ms in the endpoint table and 4 to 5 ms in the record push; half of the push was indexing the 72 hour vectors. Consecutive lines almost always share an hour (on seed 1, 1,054 hour changes in 3.1 million lines), so the parser now keeps the current hour's records in a local, swaps them back only when the hour changes, and writes records through a raw pointer with the length held in a local. No ordering is assumed: every hour change takes the slow path.

Local x86 VM paired medians against the prior source: 0.9673 / 0.9711 / 0.9741 at 8 / 12 / 20 threads (41 rounds, seed 801) and 0.9787 / 0.9820 / 0.9780 (61 rounds, seed 802). It passed `experiments/a-x86-speed/check.py` (14 of 14) and `adversarial.py`, and the scalar build passed `adversarial.py --quick`. In the same pass these were rejected: a three-word endpoint hash (1.003 to 1.019), two interleaved parse cursors (1.006 to 1.021), direct percentiles for groups of one or two (noise; see `experiments/a-x86-speed-2/`), and removing `MADV_DONTNEED` (1.026 to 1.050). The source grows from 496 to 519 lines. These are local measurements, not official scores. Details: `experiments/a-x86-speed-3/README.md`.

## Board results for the x86 work (2026-10-31 to 11-01)

These are the board's figures as reported by the team. Run IDs are listed where they were recorded in commit messages. The run IDs for the PR #4 and PR #10 runs were not recorded and should be added from the board.

| Trial | Commit | Board run | T | M | S | K | Decision |
|---|---|---|---:|---:|---:|---:|---|
| PR #4 x86 speed pass, three runs | `128a825` | not recorded | 27.1 / 28.0 / 28.1 ms | 22.2 to 24.7 MB | | 39.20 / 39.35 / 39.31 (prior 38.21 at T 32.9 ms) | kept |
| PR #10 line trim | `171ca6f` | not recorded | 24.75 ms | | 474 to 414 | 41.70 to 42.42 | kept |
| PR #19 allocator settings | `e51faa2` | `run-c264b6df5fe3` | not faster | 65.6 MB (from about 22) | | 32.79 | reverted in `e4308ed` |
| PR #21 newline-mask line stepping | `35b31fd` | `run-155bb12513d7` | 26.8 ms | | | 40.16 (same-code range 40.6 to 42.6) | reverted in `80882e1` |

PR #4's speedup on the box (about 16% in T) fell short of the local 8-thread estimate (about 22%), and most of its K gain was taken by the added lines (S). PR #10 confirms that S is a large factor at this point: 60 fewer lines raised K by 1.7% at about the same T.

### PR #19: allocator settings (rejected)

A phase profile of `98c96ce` on the local VM found parse threads waiting about 2 ms for page faults: every buffer of 128 KiB or more was its own mmap and munmap, and both take the memory-map lock for writing. The trial kept buffers in the malloc heap (`mallopt`: `M_MMAP_THRESHOLD` and `M_TOP_PAD` 32 MiB, `M_TRIM_THRESHOLD` `i32::MAX`) and gave pages back with `MADV_DONTNEED` before each free. Locally it measured paired medians 0.85 / 0.84 / 0.73 at 8 / 12 / 20 threads, with only 1 to 2 MB more sampled peak `RssAnon`. On the board M rose to 65.6 MB and T did not improve. Two likely reasons, both unverified because the box's kernel version and huge-page setting are unknown:

- Since Linux 6.4 most page faults take per-VMA locks, so the stalls seen on this VM's 6.1 kernel probably do not happen on the box.
- The box's memory accounting counts heap memory that the local sampler did not see, for example because transparent huge pages are set to `always` there.

Details: `experiments/a-profile-2/README.md`.

### PR #21: newline-mask line stepping (rejected)

A one-thread CPU attribution of `e4308ed` showed that the parse loop ran as one dependency chain: each line's start was known only after its latency had been parsed. Taking line ends from a 64-bit AVX2 newline mask broke that chain. Locally, one-thread CPU fell by 17% (118.7 to 98.2 ms) and wall time by 3 to 5% at 8 to 20 threads, with 7 more lines. On the board T was 26.8 ms and K 40.16, below the same-code range.

### Lesson

Two local gains in a row, one from removing kernel lock waits and one from cutting parse CPU, did not carry over. By a rough bound, the box's T of about 25 ms is well above its CPU-only floor, so local profiles no longer predict where the box spends its time. The next step is to measure on the box itself (`experiments/a-box-probes/`). Details: `experiments/a-cpu-profile/README.md`.

Board trials, 1 Nov 2026: PR #30 (`a-mem`, hours streamed during the parse, pooled buffers, S 468) ran `run-69ed99a53619` at `aa5ab52` (T=26.85 ms, M=20.96 MB, K=40.50) and `run-3d499d7c63a1` at `6673d40` (T=25.28 ms, M=20.05 MB, K=42.11). Both runs fall inside production's same-code range (41 to 42.6) and neither beats the 42.59 best (`run-713461e1b8d4`), so it was not kept. The production src stays at `5eaefdc`. Unchanged production A in the same window: `run-90beb08eea0d` K 37.36, `run-d17ebc19d237` K 39.23, `run-0013a51c249d` K 37.60. The board was slow for A in that window.

- Nov 1 2026: opt6 cand 1 (hour-block store) bc3b070 run-eeafa197aa2f T 27.2 ms M 20.5 MB S 415 K 41.12. opt6 cand 2 (mallopt M_MMAP_THRESHOLD 64 KiB) c881b28 run-be30db50f1f7 T 25.9 ms M 20.4 MB K 42.20; b04d236 run-b45631c463b4 T 30.4 ms M 20.3 MB K 39.02 (slow box). M -2.5 MB real, T inconclusive; reverted to production for now.

- Nov 1 2026: opt6 hour-block store + 2 KiB prefetch probe 9313ee3 run-b09a7d9a032c T 28.8 ms M 20.8 MB K 39.88: prefetch does not help on the box; memory-latency reading not supported. Reverted.
- Nov 1 2026: PR #41 a-direct (O_DIRECT output) 0da83ae run-4f0849dc691c T 33.0 ms M 21.1 MB S 512 K 35.98. M unchanged (/out refuses O_DIRECT, output stays charged). Reverted.

### PR #47 shared OnceLock endpoint dictionary (Nov 1 2026, kept)
- f888b90 run-2cbfc20aac8c: T 26.3 ms, M 24.0 MB, S 405, K 40.70
- 632f485 run-8a26a2326c3e: T 25.1 ms, M 23.0 MB, S 405, K 41.96
- Mean 41.33 vs same-session previous A 41.26 / 39.64. Lower T and S; M +1-2 MB. Now production A.

- Nov 1 17:36 PST: PR #49 (N-1 summary workers + output buffer pool) KEPT, now production A. 250810b run-ba959add6f72 T 23.3 ms M 22.0 MB S 419 K 43.80; ad553c0 run-5c193abf8440 T 22.9 ms M 22.1 MB K 44.09. Mean 43.94 vs #47 same-period 40.08/40.74.
- Nov 1 2026: build-time PGO, c3c3056 run-dfe59f091862 T 23.1 ms M 22.5 MB S 438 K 43.48 (production mean 43.94). Not kept; Dockerfile lines count in S.
- Nov 1 2026: PR #54 run 1, 59a7b54 run-214450429918 T 30.6 ms M 22.8 MB S 419 K 37.90 — likely noisy batch (same batch unchanged B T 162.9 ms K 29.26); run 2.
- Nov 1 2026: PR #54 run 2, 58495d4 run-a71351c31c85 T 28.7 ms M 22.6 MB K 39.19 — noisy batch (same batch B T 192 ms K 26.93, D T 151). Restored #49 A src as control.
- Nov 1 2026: control #49 at 66bb4d8 run-1d571e6cb3dd T 22.9 ms M 22.3 MB S 419 K 44.09 (same batch B still slow, T 192). #54 NOT kept (37.90/39.19, T 30.6/28.7 vs control 22.9); A stays #49.

## Nov 2 opt12 (VM-profiled) trials
- 121c04a cand (prod + hour-key compare + lazy dictionary/per-thread cut): run-34860157f325 T 24.39 ms, K 42.30; 29fbafd rerun run-2ac371de9532 T 24.22, K 42.68. Tie with prod (41.75/43.12).
- 339bc5a cand2 (S-trim + same two changes, S 332): run-a1f859080567 T 24.08 ms, M 22.11 MB, K 44.55. Rerun pending.
- 7c120d2 cand2 rerun: run-ffcee18939e1 T 22.45 ms, M 23.31 MB, S 332, K 45.65. KEPT as A production (44.55/45.65 vs prod 41.75-43.12).
- c733a49: run-6fa01abe4c90 T 22.50 ms, M 22.68 MB, K 45.85.
- cbd0e02: run-8a97c4946f70 T 25.24 ms, K 43.45 (noise).
