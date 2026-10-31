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

The unchanged Linux candidate subsequently matched the published full seed-1 SHA-256 in a restricted offline ARM Linux container. The new target-machine source count, time and cgroup memory still require an official practice run.

`track-a-verification/latency_grid_test.py` additionally checked 132,624 singleton groups across all 72 hours and 1,842 endpoints, random unsigned-32-bit latencies of every decimal width, 0 and 4294967295, and 1, 2, 6, 12 and 64 workers. This used the same Darwin-only test adaptation.
