# Track B: performance log

Every step from the reference to the current version. Board run IDs get filled in once the steps run on the live board.

**Local setup for every number below:** an arm64 Linux VM with 2 cores, shared with other jobs, so wall times are noisy. Where a phase is named, the CPU time comes from `CLOCK_PROCESS_CPUTIME_ID`. Peak RSS comes from `getrusage` (`ru_maxrss`; it counts the corpus pages mapped from the file). The dataset is `full`, seed 1 (250,000 docs, 50,000 queries). Every kept step produced sha256 `f86973c2…4e80927`, which matches the spec.

The reference on this VM: **97.6 s wall, 2,093 MB** at `full`; 10.5 s and 295 MB at `sample`.

| Step | Change | Run ID | T local (s, 2 cores) | CPU (s) | M local (MB) | Points |
|---|---|---|---|---|---|---|
| 0 | The reference, unchanged | | 97.6 | ~97 | 2,093 | 0 |
| 1 | Rust v1: query terms only, FNV dict, `Vec<Vec<u32>>` postings per thread, BOOL on bitmaps, phrases verified by re-tokenizing candidate docs | | 6.2 | index 6.5 + query 8.0 | 377 | |
| 2 | Dict keyed by the token packed into 4×u64, with a cheap multiplicative hash | | ≈5 | index 4.7 | 377 | |
| 3 | Postings: per-doc stream of distinct term ids, then a counting sort into CSR (no per-term `Vec` growth) | | ≈4.5 | index 3.6 | 377 | |
| 4 | Lazy shared bitmaps (`OnceLock`) for terms with df > N/32 | | ≈4.3 | BOOL 3.6 → 0.4 | 380 | |
| 5 | Phrases checked during the scan around the rarest term (chosen from a sample); no rescan, no positions | | 2.2–2.6 | total 13 → 4.7 | 377 | |
| 6 | Sample 2 MB → 512 KB; slot table sized from the query word count | | 2.1–2.6 | serial pre-phase 69 → 41 ms | 398 | |
| 7 | `madvise(MADV_DONTNEED)` on each 4 MB slice after it is scanned | | 2.2–2.8 | unchanged | **139–177** | |
| 8 | Query phase: 4 static blocks per thread instead of an atomic work counter (simpler, same speed) | | same | same | same | |

Current local result: **2.2 s wall on 2 cores** (best of 3), 5.3 s pinned to one core. That is about 44× the reference on the same VM. Peak RSS is about 150 MB, about 14× lower. `sample` runs in 0.15 s with 12 MB.

## Where the time goes (one core, full)

- Tokenizing 254 MB alone (finding token boundaries and building keys): about 0.6 s.
- Dictionary lookups for 36.5 M tokens: about 1.5 s. A 32 KB slice of the corpus, re-scanned until it is hot in cache, does the same lookups in a third of the time. So the lookups are limited by memory latency, not instruction count. Probing is not the problem: there were 6.1 M extra probes over 36.5 M lookups.
- Stream, counting sort and phrase checks: about 1.2 s.
- BOOL evaluation and output: about 0.4 s across threads.
- Serial work before the scan (reading the queries, the dict, the sample): about 40 ms. This is the part that does not get faster with more threads.

## Experiments that did not help

- **Keys stored in the slots** (40-byte entries, one cache line per lookup instead of slot → key): no gain, slightly slower (5.1 s vs 4.3–4.8 s CPU on one core). The bigger table (5 MB vs 1 + 2.4 MB) loses as much locality as the saved indirection gains. Reverted.
- **Branch-free key comparison** (XOR/OR of the four words instead of the derived `==`): no change. Reverted.
- **Smaller slot table** (2^18 instead of 2^20 slots): no measurable change in lookup cost. Kept the size computed from the query word count only because it allocates less.
- **SWAR key build** (`| 0x20` on 8-byte loads instead of a per-byte shift into the key): neutral on this VM. Kept because it is simpler and has no store-forwarding chain.
- **`MAP_POPULATE`**: it pre-faults the whole map in one serial kernel call (14 ms) instead of letting the scan threads fault pages in parallel, and it conflicts with releasing slices. Not used.
