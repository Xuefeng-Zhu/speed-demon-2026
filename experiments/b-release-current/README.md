# B mapped-page release ablation against dense-summary baseline

The candidate omits periodic MADV_DONTNEED calls from the selected B scan. Input and result computation, bounded phrase summaries and bitmap caps are otherwise unchanged. It leaves unused declarations in this isolated source; this is not a submission candidate. The baseline is the selected dense-summary source.

Seven measured randomized native Mac ARM pairs after warmup all matched the published full-seed SHA-256. Median wall was 0.269821 s candidate versus 0.275589 s baseline, while median CPU was 1.588603 versus 1.576897 s. The small wall difference and opposite CPU direction under potential shared-host activity do not establish a win; ARM uses scalar tokenization rather than x86 AVX2. The candidate can retain more file-backed pages, and native process RSS is not the official warmed-cgroup peak. Compare on x86 with cgroup accounting before any consideration; no alternate-reference or collision testing was done because the result was inconclusive. Raw data is `report.json`.

Compile both sources with matching release/target flags and use `python3 experiments/b-rust-lengthhash/compare.py --baseline /path/to/base --candidate /path/to/candidate --data /path/to/full-b --runs 7 --report /tmp/b-release.json`. Generate input independently; no Mac Docker was used.
