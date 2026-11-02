# Track C: smaller reader and event buffers

Current Track C already reads records through bounded positioned-read buffers.
This change reduces the normal per-worker read buffer from 64 KiB to 32 KiB and
the producer event-block capacity from 1024 to 512. Long unfinished records
still grow the buffer through the existing refill logic. The CSV parser, owner
hashing, country membership, ordering and aggregation are unchanged.

The baseline source is SHA-256
`63623afc7294b64831e7645ea55a56be724639baa7cf50544039dd44d312ddce`
at `c7ebe6d` (also unchanged at PR base `f14778b`). The tested candidate is
`5675f5068478fe2538a92297b4009da1d0b11f13c38f9bc31218cb11dc25c97f`.
Neither constant replacement changes formatted Rust line count or dependencies.

## Independent native confirmation

Rust 1.99.1, the production pinned compiler/runtime images and Cargo flags;
native Xeon Platinum 8573C, six physical cores/twelve SMT threads, CPUs 0–11.
Each run uses a fresh restricted container, warmed input, no network, read-only
root/data, uid 65534, an 8 GiB/no-swap limit and ordinary default allocator
settings. Builds and runs are serialized. The child-process timer excludes
Docker startup; the same small waiting parent contributes to both cgroup peaks.

| Twenty measured pairs per seed | Seed 1 | Seed 2 |
| --- | ---: | ---: |
| Median within-pair wall change | +0.68% | +0.54% |
| Median within-pair process CPU change | +1.62% | +1.28% |
| Median within-pair cgroup peak change | -16.43% | -15.36% |
| Observed maximum cgroup peak, baseline → candidate | 13.609 → 11.207 MiB | 13.367 → 11.391 MiB |

All 84 executions, including four excluded warmup executions, matched complete
reference output hashes. An earlier independent nine-pair-per-seed screen also
matched all 40 outputs and showed the same direction: +0.69%/+0.68% wall,
-19.08%/-15.39% paired cgroup peak. The two changes were screened separately
before combining them.

These are VM measurements, not official scoring-box results. Median paired
changes and observed maxima are different summaries and are labeled separately.
Smaller requested payload alone does not explain the entire charged-memory
difference; queue overlap and allocator behavior were not causally isolated.
The time/memory tradeoff still needs Board confirmation. No official K gain is
claimed, and any score estimate must apply the official memory cap.

`results.json` preserves the independent confirmation's input, source and binary
hashes, compiler identity, all individual timing/resource rows and the summary.
Data paths and remote connection details are omitted.

## Correctness and reproduction

The baseline and final candidate each passed 132 direct organizer-reference
comparisons: 33 CSV fixtures at 1/2/7/12 workers. Fixtures cover quoted commas,
escaped quotes, embedded newlines, mixed CRLF/LF, BOMs, unknown regions, numeric
widths, an unterminated final record, long names/notes crossing both buffer
sizes, buffer doubling, and concentrated producer events.

Build the baseline at `c7ebe6d` and candidate with their unchanged Dockerfiles,
then extract each `/app/solution` binary. On an idle native x86 Linux host with
AVX2, AES and PCLMULQDQ, reproduce the reference checks with:

```sh
python3 experiments/c-buffer-memory/verify.py /absolute/baseline /absolute/candidate \
  --workers 1,2,7,12 --report /tmp/c-buffer-verification.json
```

Use the pinned runtime and the container restrictions above for performance
comparisons. Generate full seeds with `official/generators/c_join.py`; seed 1's
expected hash is published and seed 2's saved hash came from the organizer
reference. Warm the data on the host, interleave complete baseline/candidate
runs in randomized order, and measure exec-to-exit wall plus cgroup
`memory.peak` rather than RSS. The binary build flags are `opt-level=3`, fat LTO,
one codegen unit, panic abort, `x86-64-v3,+aes,+pclmulqdq`, with no PGO.
