# Board results for the A probes (Oct 31 2026, practice runs)

Base (production A, 80882e1 src): best run-713461e1b8d4 T 24.86 ms, typical 24.4-25.9 ms.

| Probe | Commit | Run | T | M | K | Reading |
|---|---|---|---:|---:|---:|---|
| stderr | ee52063 | run-14adda073ae8 | 31.15 ms | 22.7 MB | 37.32 | board.json exposes no stderr; slower than base (noise or stderr cost) |
| threads12 | 9f84c31 | run-620823962f88 | 25.58 ms | 22.9 MB | 41.49 | no gain over 20 threads |
| threads14 | 688bfb8 | run-e732da77d8cc | 25.90 ms | 23.1 MB | 41.18 | no gain over 20 threads |
| parse2 | dd40d21 | run-998e65c9f07e | 42.07 ms | 31.8 MB | 30.31 | parse wall >= ~17 ms (about 2/3 of T) |
| sum2 | 67a5256 | run-214a3b2ac447 | 29.73 ms | 30.3 MB | 36.33 | summary wall >= ~5 ms |

Conclusion: the box spends most of T parsing; capping threads does not help. Next A work should target parse (or overlap summary with parse), not thread count.
