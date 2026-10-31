# 1,024-key exact window plus radix overflow (experimental, not selected)

This variant of `../track-d-window-radix/` uses a 1,024-key aligned window and drains radix buckets 0–10. Baseline is exact restored D source at `451429c`. It passed 100,000 modeled heap operations with debug and overflow assertions and all full seed-1 hashes; separate graph-oracle and independent proof tests have not been performed for this window size.

Seven shared ARM native pairs (`report.json`) gave median 0.34818 s candidate vs 0.29947 s baseline, CPU 2.14992 vs 1.77983 s, peak native RSS 536,231,936 vs 535,527,424 B. This slower screen is not an x86 or official cgroup result; candidate remains unselected. No Mac Docker was used.
