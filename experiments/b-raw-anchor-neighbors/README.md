# Raw-neighbor phrase experiment

This isolated experiment streams Boolean postings while scanning each document and
checks candidate phrases by scanning the raw neighboring token bytes. A per-document
2,048-unit work budget triggers a full original-style phrase replay. Partial hits
are deduplicated by document. The common path avoids materializing the token-ID
vector; the replay retains the original per-document storage bound.

Do not promote this version: native ARM full-seed screening found a regression.
With nine randomized paired measurements after one warmup, median wall time was
0.23550 s baseline versus 0.26433 s candidate (12.2% slower); median CPU was
1.51947 s versus 1.76764 s (16.3% more). This is a shared native machine result,
not an official x86 score. `arm-screen.json` preserves all timing samples.

Both source files were compiled with `rustc --edition=2021 -O -C lto=fat
-C codegen-units=1 -C panic=abort`. All 20 executions in the full comparison
matched seed 1's expected SHA-256. The candidate additionally passed 40 small
differential corpora, six long-document boundary cases, and a 250,000-document
duplicate-query test. These checks are incomplete: in particular, forced budget
exhaustion and replay after partial hits have not been explicitly verified.

Baseline SHA-256: `7d371fe84ce9f0fd9d3c7e6fdf02b6b37e0f1440319c654161b990cf27bb8bf3`.
Candidate SHA-256: `5a3c6985ceafec26b18b462150367bd76aa8cca9fafdd8be05768e777752e2b2`.
