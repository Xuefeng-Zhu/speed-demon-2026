# Performance and correctness log

No official board run IDs have been recorded; timings below are local, not official scores. The board app is installed.

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
