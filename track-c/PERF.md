# Track C performance log

| Step | Change | Run ID | T (s) | M (MB) |
|---|---|---|---|---|
| 0 | Organizers' Python reference | — | 14.44 | 367 |
| 1 | C++ byte parser, direct region map, per-country distinct-name sets | Not run on board | Not measured on board | Not measured on board |

Local validation and local timings are in README.md. No live-board runs have been made; do not substitute laptop timings for board measurements.

Local revision after step 1: keep canonical name byte views into the input buffer, count note bytes without allocation, and read files directly into a sized buffer. Three interleaved Mac runs improved from 2.833–4.802 s to 1.611–2.730 s; measured peak RSS fell from 687.5–808.9 MB to 354.9–359.3 MB. Other experiments ran concurrently, so repeat on an idle machine. Published seed 1 full and sample hashes and independent reference comparisons still match. These are not board measurements.

## Controlled local comparison

Five interleaved full-data pairs after warmup on macOS ARM: original median 2.636044 s, current median 1.499528 s (1.76×). Every output matched the full hash. Details: `experiments/bench-c.json`. These are local measurements, not board scores.

Local revision after the hash-set variant: append name views to per-country vectors, then sort and deduplicate. Two interleaved full-data pairs produced 2.641/1.938 s and 352.0/354.6 MB peak RSS for the hash-set version versus 1.142/0.709 s and 293.5/293.0 MB for this variant. All outputs matched the published SHA-256. Other work ran concurrently. The final candidate also passed the restricted ARM Linux Docker full-data check in 1.27 s including startup; these figures are not board measurements.

## Native x86 dot VM

The candidate and original were tested on the full seed-1 dataset with GCC 14. See `experiments/dot-vm.md` for the five-run medians and limitations. This was not a board run.
