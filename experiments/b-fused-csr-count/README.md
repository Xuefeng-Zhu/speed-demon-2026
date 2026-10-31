# Fused CSR count experiment

This isolated experiment counts CSR term occurrences during tokenization to remove a separate stream pass. On the shared ARM host, 11 paired full-seed runs gave baseline median 0.24515 seconds and 1.56684 CPU seconds versus candidate 0.24667 and 1.57425. All 24 full outputs including warmups matched the expected hash. There was no measured speed win; no broader correctness or x86 tests were run, and this candidate was not selected. Raw measurements are in `report.json`.
