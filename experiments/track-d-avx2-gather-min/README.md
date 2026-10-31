# D AVX2 gather for radix-bucket minimum (unselected, unvalidated on x86)

This isolated hypothesis changes only the scan that finds the minimum in a nonempty radix-heap bucket. `baseline.rs` is the exact selected packed-adjacency D source, SHA-256 `793d13729fe4dabe2a1ed272fef78e19567456676ed8df52c075bc4ac33ebd05`; `meeting.rs` is SHA-256 `8d57095daa927d5e9f309c38d897d7ee0b771f29b54d06e873b05e45ff126772`. For `x86_64` builds with AVX2 and 16-byte tuple stride, the helper gathers four initialized u64 key fields at a time. It does not read uninitialized tuple padding. XORing the sign bit permits signed AVX2 comparisons to implement the full unsigned u64 order. A scalar tail handles remainders, and all other architectures/compilation targets use the original scalar minimum. Bucket ordering and all graph/search code are otherwise unchanged.

The reason to investigate is prior instrumentation in `experiments/track-d-query-profile2/`, which counted 32.5 million redistributed bucket entries on one public-seed run. This does not measure time spent finding minima and **does not establish a speedup**; AVX2 gather may be slower than scalar loads. This candidate has not been independently reviewed for Rust pointer provenance or tested on actual x86 hardware, Linux protected pages, full-size data, hidden seeds or the official board. In particular do not promote it based on the evidence here.

On native macOS ARM, an overflow-checked scalar-fallback build passed 80 random directed-graph Dijkstra references / 16,000 queries. An overflow/debug-checked helper property test passed 65,664 minima over lengths 1–513, offsets 0–3, random keys, ties, zero, the signed boundary and `u64::MAX`. These tests **do not exercise the AVX2 path**. The exact extracted helper cross-compiled to x86-64-v3 Windows assembly without linking and emitted `vpgatherqq`, `vpcmpgtq`, and `vpblendvb`; this establishes code generation only, not x86 execution, correctness or performance. No benchmark is claimed, and no Mac Docker was used. The brief helper builds and oracle overlapped another agent's ARM timing screen around 10:42 UTC on 2026-10-31; that separate screen must be treated as contaminated unless its timestamps prove otherwise.

For a Linux x86-64-v3 VM with the target CPU features, run from the repository root:

```sh
python3 experiments/track-d-avx2-gather-min/verify.py --extremes
python3 experiments/track-d-avx2-gather-min/compare.py --data /path/to/full-seed-1 --build-dir /tmp/d-gather-build --report /tmp/d-gather-a.json --runs 15
python3 experiments/track-d-avx2-gather-min/compare.py --data /path/to/full-seed-1 --build-dir /tmp/d-gather-build --report /tmp/d-gather-b.json --runs 15
```

`verify.py` runs both generic and x86-64-v3 builds, asserts that the executable contains `vpgatherqq`, checks unsigned helper properties and Linux protected-page boundaries, and runs graph-oracle, exhaustive graph, and packed adjacency boundary tests. `--extremes` adds the full-size maximum-weight chain. Independently review the actual gather pointer/provenance and guard behavior before selection. `compare.py` verifies the public full output hash on every warmup and measurement and reports native process RSS, not cgroup memory. Run measurements serially on an AVX2-capable machine, then perform official practice only if review and target results justify it.
