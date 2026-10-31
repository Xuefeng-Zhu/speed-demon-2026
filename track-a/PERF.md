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

From the workspace root, rebuild the preserved baseline and final candidate with the same local compiler and run a paired, alternating comparison:

```sh
c++ -O3 -std=c++17 -o /tmp/track-a-baseline track-a-agent/main.cpp
c++ -O3 -std=c++17 -o /tmp/track-a-final track-a/main.cpp
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
INGEST_BINARY=/tmp/track-a-final python3 track-a-verification/test.py
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

`track-a-verification/latency_grid_test.py` additionally checked 132,624 singleton groups across all 72 hours and 1,842 endpoints, random unsigned-32-bit latencies of every decimal width, 0 and 4294967295, and 1, 2, 6, 12 and 64 workers. This used the same Darwin-only test adaptation.

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
