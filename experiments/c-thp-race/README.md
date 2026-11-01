# Track C: why the prefault raised M (huge-page fault races)

## Board observation

After #26 (prefault of each owner's slots), Track C got faster but its memory peak rose:

| source | run | T | M |
|---|---|---:|---:|
| `d61a2e1` (#23) | `run-603a0d204651` | 41.0 ms | 13.8 MB |
| #26, production since `ee52063` | `run-38899e5ae2f9` | 36.8 ms | 17.2 MB |
| same | `run-0d1302f06ed0` | 36.5 ms | 16.0 MB |
| same | `run-949821fd83fb` | 36.7 ms | about 18.0 MB, implied by its K |

On the sandbox, process max RSS did not change: a median of 11.7–12.1 MB both before and after #26. The extra board memory was therefore never mapped into the process.

## Mechanism

The harness reads `memory.peak` of the run's cgroup, which counts every page charged to the cgroup. When a thread faults an empty, huge-page-eligible 2 MiB range, the kernel follows these steps:
1. It allocates a 2 MiB folio and charges it to the cgroup.
2. It zeroes the folio.
3. Only then does it take the page-table lock and check whether another thread has already installed a huge page there. If one has, it frees its own folio.

So when *k* threads fault the same empty range at once, the cgroup is charged *k* × 2 MiB for a moment, while only one huge page ends up mapped. Zeroing 2 MiB takes long enough to make this window wide.

`thp-race.rs` reproduces this. On the sandbox kernel (6.1), eight threads first-wrote the same MADV_HUGEPAGE range at once, three times:

| threads | advice | pages allocated | pages freed | huge pages installed |
|---:|---|---:|---:|---:|
| 1 | 14 (huge) | 523–531 | 0–6 | 1 |
| 8 | 14 (huge) | 3,144–4,214 | 2,567–3,599 | 1 |
| 8 | 15 (no huge) | 83–114 | 2–138 | 0 |

The #26 prefault follows exactly this pattern. On the board's 12 threads, each owner's share of the name table is about 427 KiB, so about five owners share each huge page, and all of them write their slots as soon as they start. Before #26, an owner's first access to a slot was a read. On the sandbox kernel, a read fault maps the shared huge zero page, which is not charged to the cgroup, and the later write splits it into 4 KiB pages. The board runs Debian 13's 6.12 kernel, which we expect to behave the same way; this was not verified.

## Measurement

`vmdelta.rs` records page-allocation deltas from `/proc/vmstat` around each run. To keep background noise low, the builds tested here exit right after the two regions passes. That is where the prefault and the concurrent region-table writes happen. The runs used 8 threads, 150 runs per build, interleaved:

| build | runs that allocate ≥ 400 pages above the median (≥ 1 discarded huge page) | p90 pages | worst run |
|---|---:|---:|---:|
| production (#26) | 19/150 and 24/150 (two batches) | 2,317 / 2,337 | +2,078 pages above the median (about 4 huge pages, 8 MiB) |
| this change | 3/150 and 4/150 | 1,953 / 1,990 | +735 |
| no huge pages anywhere (advice 15 on both maps) | 2/150 | 1,913 | — |
| an empty program | 0/150 | — | — |

Builds without huge pages still show 2–4 runs out of 150 above the threshold. Those come from other activity on the machine. On the board, M is the largest of five peaks, and there are about five owners per huge page instead of three, so a racing run becomes more likely.

## Change

- **One first writer per huge page.** `zeroed` writes one byte per 2 MiB on the calling thread (the main thread) right after mapping. Each huge page of the name table is therefore faulted in before any worker exists. The owners' prefault is kept: inside huge pages it finds the pages already present, and at the table's edges it faults 4 KiB pages, where a lost race costs at most 4 KiB.
- **No huge pages for the region table.** The region table gets MADV_NOHUGEPAGE. All threads fill it at once in the second regions pass. At 1 MB it cannot fill a huge page by itself, but with the same advice as the name table the two adjacent mappings can merge into huge-page-eligible ranges, as they did on the sandbox.

## Alternatives measured

All on the sandbox, 8 threads, interleaved 30–40-round batches, compared with production:

| variant | time | formatted lines |
|---|---:|---:|
| this change | +0.4% to +0.9% (the main thread zeroes one or two huge pages before spawning) | +3 |
| designated worker per 2 MiB range, which the others skip | about +0.7% | +9 |
| no huge pages at all (advice 15 on both maps) | +1.0% to +1.5% (more TLB misses) | 0 |

Single-thread time and process max RSS are unchanged. Reference checks pass under 1, 3, 5 and 8 threads, including a build that starts from 2^6 slots and restarts repeatedly.

## Other tracks

Track D's `zeros()` marks the interior of a `Vec` MADV_HUGEPAGE, and its threads write those arrays at once through `atomic()`. If more than one thread first-touches the same 2 MiB range, the same race would add discarded huge pages to D's M. This was not checked or changed here.
