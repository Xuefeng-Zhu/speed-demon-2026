# Track B isolated follow-up

Native macOS ARM, shared system load. All full-data runs matched published SHA-256 `f86973c210228141bcb6f1f1b10188ad2a9b65f71e7cd7cf4590b38de4e80927`. These are exploratory per-process measurements, not official cgroup or x86 scoring.

- `b-anchor-find.cpp`: find the rarest phrase anchor inside each candidate document before verifying the full phrase. Five paired medians were 1.313938 s variant versus 1.286305 s zero-copy baseline. Tiny seed 99 and the 1,000-query edge fixture matched reference. It is slower locally; do not select. Raw `b-anchor-report.json`.
- `b-workers-{3,12}.cpp` against six-worker zero-copy baseline: four rotated runs each. Median wall / maximum process RSS: 3 workers 1.521087 s / 480,559,104 B; 6 workers 1.153274 s / 490,356,736 B; 12 workers 1.168051 s / 514,654,208 B. Six is preferred locally. Raw `b-workers-report.json`, runner `b-workers-measure.py`.
- `b-chunk-{64k,4m}.cpp` against 1 MiB zero-copy baseline: four rotated runs each. Median wall / maximum process RSS: 64 KiB 1.232215 s / 483,393,536 B; 1 MiB 1.202827 s / 490,782,720 B; 4 MiB 1.125181 s / 543,670,272 B. The time/memory factors relative to 1 MiB are ~0.991× for 64 KiB and ~1.013× for 4 MiB. The margins are small and load was variable, so retain 1 MiB. Raw `b-chunk-report.json`, runner `b-chunk-measure.py`.

No repository files were edited and no push, submission, or permissions change was performed.
