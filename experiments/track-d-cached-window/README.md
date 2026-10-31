# Cached exact-window priority queue (unselected)

The candidate changes only the queue in the positioned-read baseline. A rolling 4,096-key exact window holds vertex IDs and a two-level bitmap, an exact binary heap handles later keys, and a cached minimum avoids recomputing the selected side's top when popping. All state is derived at runtime. There has been no independent heap proof, model stress or comprehensive graph verification.

Overflow-checked candidate passed 80 random directed graphs / 16,000 oracle queries. All 16 warmup and measured full-seed hashes matched. Seven paired shared ARM measurements (`report.json`) gave 0.83678 vs 0.67358 s baseline, CPU 2.36343 vs 1.90519 s, max native process RSS 536854528 vs 535609344 bytes. Strong host contention limits wall conclusions, but CPU is substantially worse. The experiment is unselected and does not establish x86 or official results. No Mac Docker was used.
